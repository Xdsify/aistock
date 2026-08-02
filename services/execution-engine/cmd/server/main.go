package main

import (
	"context"
	"encoding/json"
	"log"
	"os"
	"os/signal"
	"strings"
	"syscall"
	"time"

	"github.com/gofiber/fiber/v2"
	"github.com/redis/go-redis/v9"
	"github.com/aistock/execution-engine/internal/order"
	"github.com/aistock/execution-engine/internal/position"
)

var rdb *redis.Client

func main() {
	redisAddr := parseRedisAddr(getEnv("REDIS_URL", "redis://localhost:6379"))
	rdb = redis.NewClient(&redis.Options{
		Addr:     redisAddr,
		Password: "",
		DB:       0,
	})

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	if err := rdb.Ping(ctx).Err(); err != nil {
		log.Fatalf("Redis连接失败: %v", err)
	}
	log.Println("Redis已连接")

	orderMgr := order.NewManager(rdb)
	posTracker := position.NewTracker(rdb)

	go subscribeSignals(ctx, orderMgr, posTracker)

	app := fiber.New(fiber.Config{
		AppName: "AI炒股-执行引擎",
	})

	app.Get("/health", func(c *fiber.Ctx) error {
		return c.JSON(fiber.Map{"status": "ok", "service": "execution-engine"})
	})

	app.Get("/api/orders", func(c *fiber.Ctx) error {
		orders, _ := orderMgr.GetActiveOrders(ctx)
		return c.JSON(orders)
	})
	app.Get("/api/orders/:id", func(c *fiber.Ctx) error {
		order, err := orderMgr.GetOrder(ctx, c.Params("id"))
		if err != nil {
			return c.Status(404).JSON(fiber.Map{"error": "订单不存在"})
		}
		return c.JSON(order)
	})
	app.Post("/api/orders/cancel/:id", func(c *fiber.Ctx) error {
		err := orderMgr.CancelOrder(ctx, c.Params("id"))
		if err != nil {
			return c.Status(400).JSON(fiber.Map{"error": err.Error()})
		}
		return c.JSON(fiber.Map{"success": true})
	})

	app.Get("/api/positions", func(c *fiber.Ctx) error {
		positions, _ := posTracker.GetAllPositions(ctx)
		return c.JSON(positions)
	})
	app.Get("/api/positions/:symbol", func(c *fiber.Ctx) error {
		pos, err := posTracker.GetPosition(ctx, c.Params("symbol"))
		if err != nil {
			return c.Status(404).JSON(fiber.Map{"error": "无持仓"})
		}
		return c.JSON(pos)
	})

	app.Get("/api/account", func(c *fiber.Ctx) error {
		equity, _ := rdb.Get(ctx, "account:total_equity").Float64()
		cash, _ := rdb.Get(ctx, "account:available_cash").Float64()
		return c.JSON(fiber.Map{
			"total_equity":   equity,
			"available_cash": cash,
		})
	})

	app.Post("/api/order/manual", func(c *fiber.Ctx) error {
		var req struct {
			Symbol string  `json:"symbol"`
			Action string  `json:"action"`
			Price  float64 `json:"price"`
			Volume int64   `json:"volume"`
		}
		if err := c.BodyParser(&req); err != nil {
			return c.Status(400).JSON(fiber.Map{"error": "参数错误"})
		}
		orderID, err := orderMgr.PlaceOrder(ctx, req.Symbol, req.Action, req.Price, req.Volume, "manual")
		if err != nil {
			return c.Status(400).JSON(fiber.Map{"error": err.Error()})
		}
		return c.JSON(fiber.Map{"order_id": orderID})
	})

	app.Post("/api/emergency-stop", func(c *fiber.Ctx) error {
		orderMgr.CancelAll(ctx)
		rdb.Set(ctx, "circuit_breaker:emergency_stop", "1", 0)
		return c.JSON(fiber.Map{"success": true, "message": "所有订单已取消,交易已暂停"})
	})

	go func() {
		sigCh := make(chan os.Signal, 1)
		signal.Notify(sigCh, syscall.SIGINT, syscall.SIGTERM)
		<-sigCh
		log.Println("执行引擎关闭中...")
		cancel()
		app.Shutdown()
	}()

	port := getEnv("PORT", "9001")
	log.Printf("执行引擎启动在 :%s", port)
	log.Fatal(app.Listen(":" + port))
}

func subscribeSignals(ctx context.Context, orderMgr *order.Manager, posTracker *position.Tracker) {
	pubsub := rdb.Subscribe(ctx, "signal:approved")
	defer pubsub.Close()

	ch := pubsub.Channel()
	log.Println("订阅信号频道: signal:approved")

	for msg := range ch {
		var signal struct {
			SignalID             string  `json:"signal_id"`
			Symbol               string  `json:"symbol"`
			Action               string  `json:"action"`
			Strength             float64 `json:"strength"`
			Price                float64 `json:"price"`
			Volume               int64   `json:"volume"`
			PositionPct          float64 `json:"position_pct"`
			StopLoss             float64 `json:"stop_loss"`
			TakeProfit           float64 `json:"take_profit"`
			RequiresConfirmation bool    `json:"requires_confirmation"`
		}

		if err := json.Unmarshal([]byte(msg.Payload), &signal); err != nil {
			log.Printf("信号解析失败: %v", err)
			continue
		}

		if signal.RequiresConfirmation {
			log.Printf("信号 %s 需要人工确认,跳过自动执行", signal.SignalID)
			continue
		}

		breakerActive, _ := rdb.Exists(ctx, "circuit_breaker:emergency_stop").Result()
		if breakerActive > 0 {
			log.Println("紧急熔断激活中,拒绝所有信号")
			continue
		}

		if signal.Volume == 0 {
			equity, _ := rdb.Get(ctx, "account:total_equity").Float64()
			if equity > 0 {
				signal.Volume = int64(equity * signal.PositionPct / signal.Price / 100) * 100
			}
			if signal.Volume < 100 {
				signal.Volume = 100
			}
		}

		orderID, err := orderMgr.PlaceOrder(
			ctx, signal.Symbol, signal.Action,
			signal.Price, signal.Volume, signal.SignalID,
		)
		if err != nil {
			log.Printf("下单失败: %v", err)
			continue
		}
		log.Printf("订单已提交: %s %s %s %d股 @%.2f",
			orderID, signal.Action, signal.Symbol, signal.Volume, signal.Price)
	}
}

// parseRedisAddr 从redis:// URL中提取 host:port
func parseRedisAddr(url string) string {
	s := url
	s = strings.TrimPrefix(s, "redis://")
	s = strings.TrimPrefix(s, "redis://default@")
	// 移除路径和查询参数
	if idx := strings.Index(s, "/"); idx >= 0 {
		s = s[:idx]
	}
	if idx := strings.Index(s, "?"); idx >= 0 {
		s = s[:idx]
	}
	return s
}

func getEnv(key, defaultVal string) string {
	if val := os.Getenv(key); val != "" {
		return val
	}
	return defaultVal
}
