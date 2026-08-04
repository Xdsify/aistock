package main

import (
	"bytes"
	"context"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"os/signal"
	"strconv"
	"strings"
	"syscall"
	"time"

	"github.com/gofiber/fiber/v2"
	"github.com/gofiber/fiber/v2/middleware/cors"
	"github.com/gofiber/fiber/v2/middleware/logger"
	"github.com/gofiber/contrib/websocket"
	"github.com/redis/go-redis/v9"
	"github.com/aistock/api-gateway/internal/ws"
)

var rdb *redis.Client
var startTime = time.Now()

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

	hub := ws.NewHub(rdb)
	go hub.Run()

	app.Get("/health", func(c *fiber.Ctx) error {
		return c.JSON(fiber.Map{"status": "ok", "service": "api-gateway"})
	})

	app.Get("/metrics", func(c *fiber.Ctx) error {
		body := fmt.Sprintf(
			"# HELP atrading_gateway_uptime_seconds Gateway uptime in seconds\n"+
				"# TYPE atrading_gateway_uptime_seconds gauge\n"+
				"atrading_gateway_uptime_seconds %d\n"+
				"# HELP atrading_gateway_ws_clients Connected websocket clients\n"+
				"# TYPE atrading_gateway_ws_clients gauge\n"+
				"atrading_gateway_ws_clients %d\n",
			int(time.Since(startTime).Seconds()), hub.GetClientCount(),
		)
		return c.SendString(body)
	})

	// REST API 代理
	api := app.Group("/api")

	// 认证中间件: 保护交易/设置/下单类路由 (公开的行情/AI/策略列表不受限)
	api.Use("/orders", authRequired)
	api.Use("/positions", authRequired)
	api.Use("/account", authRequired)
	api.Use("/equity-history", authRequired)
	api.Use("/stats", authRequired)
	api.Use("/emergency-stop", authRequired)
	api.Use("/settings", authRequired)
	api.Use("/signals", authRequired)
	api.Use("/strategy/activate", authRequired)
	api.Use("/strategy/deactivate", authRequired)
	api.Use("/strategy/create", authRequired)
	api.Use("/strategy/signal", authRequired)
	api.Use("/risk/circuit-breaker", authRequired)

	api.Get("/market/sentiment", proxyHandler("http://data-service:8001/api/data/market/sentiment"))
	api.Get("/data/market/sentiment", proxyHandler("http://data-service:8001/api/data/market/sentiment"))
	api.Get("/data/stock/list", proxyHandler("http://data-service:8001/api/data/stock/list"))
	api.Get("/market/quotes", func(c *fiber.Ctx) error {
		return c.JSON(fiber.Map{"message": "use WebSocket for real-time quotes"})
	})
	api.Get("/stocks/:symbol/kline", func(c *fiber.Ctx) error {
		return proxyRequest(c, "http://data-service:8001/api/data/kline/"+c.Params("symbol"))
	})

	api.Get("/strategies", proxyHandler("http://strategy-engine:8002/api/strategy/list"))
	api.Post("/strategies/activate", proxyHandler("http://strategy-engine:8002/api/strategy/activate"))
	api.Post("/strategies/test-signal", proxyHandler("http://strategy-engine:8002/api/strategy/test-signal"))

	// 前端统一使用 /api/strategy/* 路径 (dev 经 Vite 代理直连, docker 经网关)
	api.Get("/strategy/list", proxyHandler("http://strategy-engine:8002/api/strategy/list"))
	api.Get("/strategy/active", proxyHandler("http://strategy-engine:8002/api/strategy/active"))
	api.Post("/strategy/activate", proxyHandler("http://strategy-engine:8002/api/strategy/activate"))
	api.Post("/strategy/deactivate", proxyHandler("http://strategy-engine:8002/api/strategy/deactivate"))
	api.Post("/strategy/test-signal", proxyHandler("http://strategy-engine:8002/api/strategy/test-signal"))
	api.Post("/strategy/backtest", proxyHandler("http://strategy-engine:8002/api/strategy/backtest"))
	api.Post("/strategy/create", proxyHandler("http://strategy-engine:8002/api/strategy/create"))
	api.Post("/strategy/signal/approve", proxyHandler("http://strategy-engine:8002/api/strategy/signal/approve"))
	api.Post("/strategy/signal/quick-buy", proxyHandler("http://strategy-engine:8002/api/strategy/signal/quick-buy"))

	api.Post("/ai/sentiment", proxyHandler("http://ai-service:8003/api/ai/analyze/sentiment"))
	api.Post("/ai/pattern", proxyHandler("http://ai-service:8003/api/ai/analyze/pattern"))
	api.Get("/ai/status", proxyHandler("http://ai-service:8003/api/ai/status"))

	api.Get("/risk/status", proxyHandler("http://risk-manager:8004/api/risk/status"))
	api.Post("/risk/circuit-breaker/reset", proxyHandler("http://risk-manager:8004/api/risk/circuit-breaker/reset"))

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
	// 前端持仓页卖出用的单数路径
	api.Post("/order/manual", func(c *fiber.Ctx) error {
		return proxyRequest(c, "http://execution-engine:9001/api/order/manual")
	})
	api.Get("/positions", proxyHandler("http://execution-engine:9001/api/positions"))
	api.Get("/account", proxyHandler("http://execution-engine:9001/api/account"))
	api.Get("/equity-history", proxyHandler("http://execution-engine:9001/api/equity-history"))
	api.Get("/stats", proxyHandler("http://execution-engine:9001/api/stats"))
	api.Post("/emergency-stop", proxyHandler("http://execution-engine:9001/api/emergency-stop"))

	// 信号审批 → strategy-engine (发布 signal:approved 给执行引擎)
	api.Get("/signals", proxyHandler("http://strategy-engine:8002/api/strategy/signal/list"))
	api.Post("/signals/approve", proxyHandler("http://strategy-engine:8002/api/strategy/signal/approve"))
	api.Post("/signals/reject", proxyHandler("http://strategy-engine:8002/api/strategy/signal/reject"))
	// AI 选股 → data-service (转发到 ai-service)
	api.Post("/data/ai/screen", proxyHandler("http://data-service:8001/api/data/ai/screen"))

	// 系统设置 → 写入 Redis settings:*
	api.Get("/settings", handleGetSettings)
	api.Post("/settings", handleSettings)

	api.Post("/auth/login", handleLogin)

	// WebSocket 独立监听端口 (默认 8081)
	go func() {
		wsApp := fiber.New(fiber.Config{
			AppName: "AI炒股-API网关-WebSocket",
		})
		wsApp.Use("/ws", func(c *fiber.Ctx) error {
			if websocket.IsWebSocketUpgrade(c) {
				return c.Next()
			}
			return fiber.ErrUpgradeRequired
		})
		wsApp.Get("/ws", websocket.New(func(c *websocket.Conn) {
			ws.HandleConnection(c, hub, rdb)
		}))

		wsPort := getEnv("WS_PORT", "8081")
		log.Printf("WebSocket服务启动: :%s", wsPort)
		log.Fatal(wsApp.Listen(":" + wsPort))
	}()

	go func() {
		sigCh := make(chan os.Signal, 1)
		signal.Notify(sigCh, syscall.SIGINT, syscall.SIGTERM)
		<-sigCh
		log.Println("API网关关闭中...")
		app.Shutdown()
	}()

	port := getEnv("PORT", "8080")
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
	adminUser := getEnv("ADMIN_USERNAME", "admin")
	adminPass := getEnv("ADMIN_PASSWORD", "admin123")
	if req.Username != adminUser || req.Password != adminPass {
		return c.Status(401).JSON(fiber.Map{"error": "用户名或密码错误"})
	}
	token, err := signToken(req.Username, getEnv("JWT_SECRET", "changeme"), 7*24*time.Hour)
	if err != nil {
		return c.Status(500).JSON(fiber.Map{"error": "生成token失败"})
	}
	return c.JSON(fiber.Map{"token": token, "user": req.Username})
}

// ============ JWT (HS256, 纯标准库实现) ============

func base64url(data []byte) string {
	return base64.RawURLEncoding.EncodeToString(data)
}

// signToken 生成 HS256 JWT: header.payload.signature
func signToken(sub string, secret string, ttl time.Duration) (string, error) {
	header := base64url([]byte(`{"alg":"HS256","typ":"JWT"}`))
	now := time.Now().Unix()
	payloadObj := map[string]interface{}{
		"sub": sub,
		"iat": now,
		"exp": now + int64(ttl.Seconds()),
	}
	payloadBytes, err := json.Marshal(payloadObj)
	if err != nil {
		return "", err
	}
	payload := base64url(payloadBytes)
	signingInput := header + "." + payload
	mac := hmac.New(sha256.New, []byte(secret))
	mac.Write([]byte(signingInput))
	sig := base64url(mac.Sum(nil))
	return signingInput + "." + sig, nil
}

// verifyToken 校验签名与过期时间, 返回 sub
func verifyToken(token string, secret string) (string, bool) {
	parts := strings.Split(token, ".")
	if len(parts) != 3 {
		return "", false
	}
	signingInput := parts[0] + "." + parts[1]
	mac := hmac.New(sha256.New, []byte(secret))
	mac.Write([]byte(signingInput))
	expected := base64url(mac.Sum(nil))
	if !hmac.Equal([]byte(expected), []byte(parts[2])) {
		return "", false
	}
	payloadBytes, err := base64.RawURLEncoding.DecodeString(parts[1])
	if err != nil {
		return "", false
	}
	var payload map[string]interface{}
	if err := json.Unmarshal(payloadBytes, &payload); err != nil {
		return "", false
	}
	exp, ok := payload["exp"].(float64)
	if !ok || time.Now().Unix() > int64(exp) {
		return "", false
	}
	sub, _ := payload["sub"].(string)
	return sub, true
}

// authRequired 认证中间件: 校验 Authorization: Bearer <token>
func authRequired(c *fiber.Ctx) error {
	auth := c.Get("Authorization")
	if !strings.HasPrefix(auth, "Bearer ") {
		return c.Status(401).JSON(fiber.Map{"error": "未认证"})
	}
	token := strings.TrimPrefix(auth, "Bearer ")
	if _, ok := verifyToken(token, getEnv("JWT_SECRET", "changeme")); !ok {
		return c.Status(401).JSON(fiber.Map{"error": "token无效或已过期"})
	}
	return c.Next()
}

// handleSettings 保存系统设置到 Redis (settings:key), 各服务运行时读取覆盖环境默认值
func handleSettings(c *fiber.Ctx) error {
	var body map[string]interface{}
	if err := c.BodyParser(&body); err != nil {
		return c.Status(400).JSON(fiber.Map{"error": "参数错误"})
	}
	ctx := context.Background()
	for k, v := range body {
		switch val := v.(type) {
		case float64:
			rdb.Set(ctx, "settings:"+k, fmt.Sprintf("%g", val), 0)
		case string:
			rdb.Set(ctx, "settings:"+k, val, 0)
		}
	}
	return c.JSON(fiber.Map{"success": true, "saved": body})
}

// handleGetSettings 读取已保存的系统设置
func handleGetSettings(c *fiber.Ctx) error {
	ctx := context.Background()
	keys := []string{
		"max_single_stock_pct", "max_sector_pct",
		"daily_loss_limit_pct", "max_drawdown_pct", "ai_confidence_threshold",
	}
	result := map[string]interface{}{}
	for _, k := range keys {
		v, err := rdb.Get(ctx, "settings:"+k).Result()
		if err != nil {
			continue
		}
		if f, perr := strconv.ParseFloat(v, 64); perr == nil {
			result[k] = f
		} else {
			result[k] = v
		}
	}
	return c.JSON(result)
}

// proxyHandler 返回一个代理处理器
func proxyHandler(targetURL string) fiber.Handler {
	return func(c *fiber.Ctx) error {
		return proxyRequest(c, targetURL)
	}
}

// proxyRequest 实际执行HTTP代理请求
func proxyRequest(c *fiber.Ctx, targetURL string) error {
	// 追加原始查询参数 (如 /risk/circuit-breaker/reset?breaker_type=xxx)
	if qs := string(c.Request().URI().QueryString()); qs != "" {
		sep := "?"
		if strings.Contains(targetURL, "?") {
			sep = "&"
		}
		targetURL = targetURL + sep + qs
	}

	// 创建代理请求 (直接用原始字节, 避免 UTF-8 中文被破坏)
	req, err := http.NewRequestWithContext(
		c.Context(),
		c.Method(),
		targetURL,
		bytes.NewReader(c.Body()),
	)
	if err != nil {
		return c.Status(500).JSON(fiber.Map{"error": "代理请求创建失败"})
	}

	// 复制请求头 (跳过 Content-Length/Transfer-Encoding/Host, 交给 http.Client 管理)
	for key, vals := range c.GetReqHeaders() {
		upper := strings.ToUpper(key)
		if upper == "CONTENT-LENGTH" || upper == "TRANSFER-ENCODING" || upper == "HOST" {
			continue
		}
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
