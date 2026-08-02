package position

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/redis/go-redis/v9"
)

type Position struct {
	Symbol         string    `json:"symbol"`
	TotalQty       int64     `json:"total_qty"`
	AvailableSell  int64     `json:"available_sell"`  // 可卖 = TotalQty - LockedQty
	LockedQty      int64     `json:"locked_qty"`       // T+1锁定(今日买入)
	AvgCost        float64   `json:"avg_cost"`
	CurrentPrice   float64   `json:"current_price"`
	MarketValue    float64   `json:"market_value"`
	UnrealizedPnL  float64   `json:"unrealized_pnl"`
	RealizedPnL    float64   `json:"realized_pnl"`
	UpdatedAt      time.Time `json:"updated_at"`
}

type Tracker struct {
	rdb *redis.Client
}

func NewTracker(rdb *redis.Client) *Tracker {
	return &Tracker{rdb: rdb}
}

func (t *Tracker) HandleBuy(ctx context.Context, symbol string, qty int64, price float64) error {
	key := fmt.Sprintf("position:%s", symbol)

	pos, err := t.GetPosition(ctx, symbol)
	if err != nil {
		// 新建持仓
		pos = &Position{
			Symbol:    symbol,
			TotalQty:  0,
			AvgCost:   0,
			UpdatedAt: time.Now(),
		}
	}

	// 更新平均成本
	oldValue := float64(pos.TotalQty) * pos.AvgCost
	newValue := float64(qty) * price
	pos.TotalQty += qty
	pos.LockedQty += qty  // T+1锁定今日买入
	pos.AvgCost = (oldValue + newValue) / float64(pos.TotalQty)
	pos.AvailableSell = pos.TotalQty - pos.LockedQty
	pos.UpdatedAt = time.Now()

	return t.savePosition(ctx, key, pos)
}

func (t *Tracker) HandleSell(ctx context.Context, symbol string, qty int64, price float64) error {
	pos, err := t.GetPosition(ctx, symbol)
	if err != nil {
		return fmt.Errorf("无持仓: %s", symbol)
	}

	if pos.AvailableSell < qty {
		return fmt.Errorf("可卖数量不足: 可用%d, 尝试卖出%d", pos.AvailableSell, qty)
	}

	// 计算已实现盈亏
	realizedPnL := float64(qty) * (price - pos.AvgCost)
	pos.TotalQty -= qty
	pos.AvailableSell -= qty
	pos.RealizedPnL += realizedPnL

	if pos.TotalQty == 0 {
		pos.AvgCost = 0
	}
	pos.UpdatedAt = time.Now()

	return t.savePosition(ctx, symbol, pos)
}

// OnNewTradingDay 新交易日: 释放T+1锁定
func (t *Tracker) OnNewTradingDay(ctx context.Context) error {
	keys, err := t.rdb.Keys(ctx, "position:*").Result()
	if err != nil {
		return err
	}

	for _, key := range keys {
		data, err := t.rdb.Get(ctx, key).Bytes()
		if err != nil {
			continue
		}
		var pos Position
		if err := json.Unmarshal(data, &pos); err != nil {
			continue
		}

		pos.AvailableSell += pos.LockedQty
		pos.LockedQty = 0
		pos.UpdatedAt = time.Now()

		data, _ = json.Marshal(&pos)
		t.rdb.Set(ctx, key, data, 0)
	}

	return nil
}

func (t *Tracker) GetPosition(ctx context.Context, symbol string) (*Position, error) {
	key := fmt.Sprintf("position:%s", symbol)
	data, err := t.rdb.Get(ctx, key).Bytes()
	if err != nil {
		return nil, fmt.Errorf("无持仓: %s", symbol)
	}

	var pos Position
	if err := json.Unmarshal(data, &pos); err != nil {
		return nil, err
	}
	return &pos, nil
}

func (t *Tracker) GetAllPositions(ctx context.Context) ([]*Position, error) {
	keys, err := t.rdb.Keys(ctx, "position:*").Result()
	if err != nil {
		return nil, err
	}

	positions := make([]*Position, 0)
	for _, key := range keys {
		data, err := t.rdb.Get(ctx, key).Bytes()
		if err != nil {
			continue
		}
		var pos Position
		if err := json.Unmarshal(data, &pos); err != nil {
			continue
		}
		// 更新市值
		quoteKey := fmt.Sprintf("market:realtime:%s", pos.Symbol)
		quoteData, err := t.rdb.Get(ctx, quoteKey).Bytes()
		if err == nil {
			var quote struct {
				Price float64 `json:"price"`
			}
			if json.Unmarshal(quoteData, &quote) == nil {
				pos.CurrentPrice = quote.Price
				pos.MarketValue = float64(pos.TotalQty) * quote.Price
				pos.UnrealizedPnL = float64(pos.TotalQty) * (quote.Price - pos.AvgCost)
			}
		}
		positions = append(positions, &pos)
	}
	return positions, nil
}

func (t *Tracker) savePosition(ctx context.Context, key string, pos *Position) error {
	data, _ := json.Marshal(pos)

	// 零持仓则清理key
	if pos.TotalQty <= 0 {
		return t.rdb.Del(ctx, key).Err()
	}

	if err := t.rdb.Set(ctx, key, data, 0).Err(); err != nil {
		return err
	}

	// 发布持仓变更
	t.rdb.Publish(ctx, "position:update", string(data))
	return nil
}
