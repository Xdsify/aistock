package main

import (
	"context"
	"io"
	"log"
	"net/http"
	"os"
	"os/signal"
	"strings"
	"syscall"

	"github.com/gofiber/fiber/v2"
	"github.com/gofiber/fiber/v2/middleware/cors"
	"github.com/gofiber/fiber/v2/middleware/logger"
	"github.com/gofiber/contrib/websocket"
	"github.com/redis/go-redis/v9"
	"github.com/aistock/api-gateway/internal/ws"
)

var rdb *redis.Client

func main() {
	redisAddr := parseRedisAddr(getEnv("REDIS_URL", "redis://localhost:6379"))
	rdb = redis.NewClient(&redis.Options{
		Addr: redisAddr,
	})

	ctx := context.Background()
	if err := rdb.Ping(ctx).Err(); err != nil {
		log.Fatalf("Redis连接失败: %v", err)
	}
	log.Println("Redis已连接")

	// REST API 应用
	app := fiber.New(fiber.Config{
		AppName: "AI炒股-API网关",
	})

	app.Use(logger.New())
	app.Use(cors.New(cors.Config{
		AllowOrigins: "*",
		AllowHeaders: "Origin, Content-Type, Accept, Authorization",
	}))

	// WebSocket升级
	app.Use("/ws", func(c *fiber.Ctx) error {
		if websocket.IsWebSocketUpgrade(c) {
			return c.Next()
		}
		return fiber.ErrUpgradeRequired
	})

	hub := ws.NewHub(rdb)
	go hub.Run()

	app.Get("/ws", websocket.New(func(c *websocket.Conn) {
		ws.HandleConnection(c, hub, rdb)
	}))

	app.Get("/health", func(c *fiber.Ctx) error {
		return c.JSON(fiber.Map{"status": "ok", "service": "api-gateway"})
	})

	// REST API 代理
	api := app.Group("/api")

	api.Get("/market/sentiment", proxyHandler("http://data-service:8001/api/data/market/sentiment"))
	api.Get("/market/quotes", func(c *fiber.Ctx) error {
		return c.JSON(fiber.Map{"message": "use WebSocket for real-time quotes"})
	})
	api.Get("/stocks/:symbol/kline", func(c *fiber.Ctx) error {
		return proxyRequest(c, "http://data-service:8001/api/data/kline/"+c.Params("symbol"))
	})

	api.Get("/strategies", proxyHandler("http://strategy-engine:8002/api/strategy/list"))
	api.Post("/strategies/activate", proxyHandler("http://strategy-engine:8002/api/strategy/activate"))
	api.Post("/strategies/test-signal", proxyHandler("http://strategy-engine:8002/api/strategy/test-signal"))

	api.Post("/ai/sentiment", proxyHandler("http://ai-service:8003/api/ai/analyze/sentiment"))
	api.Post("/ai/pattern", proxyHandler("http://ai-service:8003/api/ai/analyze/pattern"))
	api.Get("/ai/status", proxyHandler("http://ai-service:8003/api/ai/status"))

	api.Get("/risk/status", proxyHandler("http://risk-manager:8004/api/risk/status"))

	api.Get("/orders", proxyHandler("http://execution-engine:9001/api/orders"))
	api.Get("/orders/:id", func(c *fiber.Ctx) error {
		return proxyRequest(c, "http://execution-engine:9001/api/orders/"+c.Params("id"))
	})
	api.Post("/orders/cancel/:id", func(c *fiber.Ctx) error {
		return proxyRequest(c, "http://execution-engine:9001/api/orders/cancel/"+c.Params("id"))
	})
	api.Post("/orders/manual", func(c *fiber.Ctx) error {
		return proxyRequest(c, "http://execution-engine:9001/api/order/manual")
	})
	api.Get("/positions", proxyHandler("http://execution-engine:9001/api/positions"))
	api.Get("/account", proxyHandler("http://execution-engine:9001/api/account"))
	api.Post("/emergency-stop", proxyHandler("http://execution-engine:9001/api/emergency-stop"))

	api.Post("/auth/login", handleLogin)

	go func() {
		sigCh := make(chan os.Signal, 1)
		signal.Notify(sigCh, syscall.SIGINT, syscall.SIGTERM)
		<-sigCh
		log.Println("API网关关闭中...")
		app.Shutdown()
	}()

	port := getEnv("PORT", "8088")
	log.Printf("API网关启动: REST=:%s, WS=:%s", port, getEnv("WS_PORT", "8081"))
	log.Fatal(app.Listen(":" + port))
}

func handleLogin(c *fiber.Ctx) error {
	var req struct {
		Username string `json:"username"`
		Password string `json:"password"`
	}
	if err := c.BodyParser(&req); err != nil {
		return c.Status(400).JSON(fiber.Map{"error": "参数错误"})
	}
	// TODO: 实际JWT验证
	return c.JSON(fiber.Map{
		"token": "jwt-token-placeholder",
		"user":  req.Username,
	})
}

// proxyHandler 返回一个代理处理器
func proxyHandler(targetURL string) fiber.Handler {
	return func(c *fiber.Ctx) error {
		return proxyRequest(c, targetURL)
	}
}

// proxyRequest 实际执行HTTP代理请求
func proxyRequest(c *fiber.Ctx, targetURL string) error {
	// 创建代理请求
	req, err := http.NewRequestWithContext(
		c.Context(),
		c.Method(),
		targetURL,
		io.NopCloser(strings.NewReader(string(c.Body()))),
	)
	if err != nil {
		return c.Status(500).JSON(fiber.Map{"error": "代理请求创建失败"})
	}

	// 复制请求头
	for key, vals := range c.GetReqHeaders() {
		for _, val := range vals {
			req.Header.Add(key, val)
		}
	}
	req.Header.Set("X-Forwarded-For", c.IP())
	req.Header.Set("Content-Type", "application/json")

	// 执行请求
	client := &http.Client{}
	resp, err := client.Do(req)
	if err != nil {
		return c.Status(502).JSON(fiber.Map{
			"error":   "后端服务不可达",
			"details": err.Error(),
		})
	}
	defer resp.Body.Close()

	// 读取响应
	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return c.Status(500).JSON(fiber.Map{"error": "读取响应失败"})
	}

	// 设置响应头
	for key, vals := range resp.Header {
		for _, val := range vals {
			c.Set(key, val)
		}
	}

	return c.Status(resp.StatusCode).Send(body)
}

func parseRedisAddr(url string) string {
	s := url
	s = strings.TrimPrefix(s, "redis://")
	s = strings.TrimPrefix(s, "redis://default@")
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
