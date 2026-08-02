package order

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/google/uuid"
	"github.com/redis/go-redis/v9"
)

type Status string

const (
	StatusPending         Status = "PENDING"
	StatusAccepted        Status = "ACCEPTED"
	StatusPartiallyFilled Status = "PARTIALLY_FILLED"
	StatusFilled          Status = "FILLED"
	StatusCancelled       Status = "CANCELLED"
	StatusRejected        Status = "REJECTED"
)

type Order struct {
	OrderID      string    `json:"order_id"`
	SignalID     string    `json:"signal_id"`
	Symbol       string    `json:"symbol"`
	Action       string    `json:"action"`
	Price        float64   `json:"price"`
	Volume       int64     `json:"volume"`
	FilledVolume int64     `json:"filled_volume"`
	AvgFillPrice float64   `json:"avg_fill_price"`
	Status       Status    `json:"status"`
	ErrorMsg     string    `json:"error_message,omitempty"`
	CreatedAt    time.Time `json:"created_at"`
	UpdatedAt    time.Time `json:"updated_at"`
}

type Manager struct {
	rdb *redis.Client
}

func NewManager(rdb *redis.Client) *Manager {
	return &Manager{rdb: rdb}
}

func (m *Manager) PlaceOrder(
	ctx context.Context, symbol, action string,
	price float64, volume int64, signalID string,
) (string, error) {
	order := &Order{
		OrderID:   uuid.New().String()[:8],
		SignalID:  signalID,
		Symbol:    symbol,
		Action:    action,
		Price:     price,
		Volume:    volume,
		Status:    StatusPending,
		CreatedAt: time.Now(),
		UpdatedAt: time.Now(),
	}

	// 存储订单
	data, _ := json.Marshal(order)
	key := fmt.Sprintf("order:%s", order.OrderID)
	if err := m.rdb.Set(ctx, key, data, 24*time.Hour).Err(); err != nil {
		return "", fmt.Errorf("订单存储失败: %w", err)
	}

	// 添加到活跃订单集合
	m.rdb.SAdd(ctx, "order:active", order.OrderID)

	// 发布订单状态更新
	m.publishOrderUpdate(ctx, order)

	// 模拟订单流程 (实际需要连接券商API)
	go m.simulateOrderLifecycle(order)

	return order.OrderID, nil
}

// simulateOrderLifecycle 模拟订单生命周期 (实际应通过broker-bridge执行)
func (m *Manager) simulateOrderLifecycle(order *Order) {
	ctx := context.Background()
	time.Sleep(500 * time.Millisecond)

	// PENDING -> ACCEPTED
	order.Status = StatusAccepted
	order.UpdatedAt = time.Now()
	m.updateAndPublish(ctx, order)

	time.Sleep(1 * time.Second)

	// ACCEPTED -> FILLED
	order.Status = StatusFilled
	order.FilledVolume = order.Volume
	order.AvgFillPrice = order.Price
	order.UpdatedAt = time.Now()
	m.updateAndPublish(ctx, order)

	// 从活跃订单移除
	m.rdb.SRem(ctx, "order:active", order.OrderID)
}

func (m *Manager) CancelOrder(ctx context.Context, orderID string) error {
	key := fmt.Sprintf("order:%s", orderID)
	data, err := m.rdb.Get(ctx, key).Bytes()
	if err != nil {
		return fmt.Errorf("订单不存在")
	}

	var order Order
	json.Unmarshal(data, &order)

	if order.Status == StatusFilled || order.Status == StatusCancelled {
		return fmt.Errorf("订单已终结,无法取消")
	}

	order.Status = StatusCancelled
	order.UpdatedAt = time.Now()
	m.updateAndPublish(ctx, &order)
	m.rdb.SRem(ctx, "order:active", orderID)

	return nil
}

func (m *Manager) CancelAll(ctx context.Context) {
	activeOrders, _ := m.rdb.SMembers(ctx, "order:active").Result()
	for _, orderID := range activeOrders {
		m.CancelOrder(ctx, orderID)
	}
}

func (m *Manager) GetOrder(ctx context.Context, orderID string) (*Order, error) {
	data, err := m.rdb.Get(ctx, fmt.Sprintf("order:%s", orderID)).Bytes()
	if err != nil {
		return nil, err
	}
	var order Order
	json.Unmarshal(data, &order)
	return &order, nil
}

func (m *Manager) GetActiveOrders(ctx context.Context) ([]*Order, error) {
	orderIDs, err := m.rdb.SMembers(ctx, "order:active").Result()
	if err != nil {
		return nil, err
	}

	orders := make([]*Order, 0)
	for _, id := range orderIDs {
		order, err := m.GetOrder(ctx, id)
		if err == nil {
			orders = append(orders, order)
		}
	}
	return orders, nil
}

func (m *Manager) updateAndPublish(ctx context.Context, order *Order) {
	data, _ := json.Marshal(order)
	m.rdb.Set(ctx, fmt.Sprintf("order:%s", order.OrderID), data, 24*time.Hour)
	m.publishOrderUpdate(ctx, order)
}

func (m *Manager) publishOrderUpdate(ctx context.Context, order *Order) {
	data, _ := json.Marshal(order)
	m.rdb.Publish(ctx, "order:update", string(data))
}
