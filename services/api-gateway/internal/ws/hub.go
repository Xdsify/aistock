package ws

import (
	"context"
	"encoding/json"
	"log"
	"sync"
	"time"

	"github.com/gofiber/contrib/websocket"
	"github.com/redis/go-redis/v9"
)

// Client 表示一个WebSocket客户端
type Client struct {
	Conn     *websocket.Conn
	Send     chan []byte
	UserID   string
	Channels map[string]bool
}

// Hub 管理所有WebSocket连接
type Hub struct {
	clients    map[*Client]bool
	broadcast  chan []byte
	register   chan *Client
	unregister chan *Client
	mu         sync.RWMutex
	rdb        *redis.Client
}

func NewHub(rdb *redis.Client) *Hub {
	return &Hub{
		clients:    make(map[*Client]bool),
		broadcast:  make(chan []byte, 256),
		register:   make(chan *Client),
		unregister: make(chan *Client),
		rdb:        rdb,
	}
}

func (h *Hub) Run() {
	// 订阅Redis频道,推送到所有客户端
	go h.subscribeRedis()

	for {
		select {
		case client := <-h.register:
			h.mu.Lock()
			h.clients[client] = true
			h.mu.Unlock()
			log.Printf("WebSocket客户端已连接 (总数: %d)", len(h.clients))

		case client := <-h.unregister:
			h.mu.Lock()
			if _, ok := h.clients[client]; ok {
				delete(h.clients, client)
				close(client.Send)
			}
			h.mu.Unlock()
			log.Printf("WebSocket客户端已断开 (总数: %d)", len(h.clients))

		case message := <-h.broadcast:
			h.mu.RLock()
			for client := range h.clients {
				select {
				case client.Send <- message:
				default:
					close(client.Send)
					delete(h.clients, client)
				}
			}
			h.mu.RUnlock()
		}
	}
}

func (h *Hub) subscribeRedis() {
	ctx := context.Background()
	pubsub := h.rdb.PSubscribe(ctx,
		"market:quote",
		"order:update",
		"position:update",
		"signal:new",
		"risk:alert",
	)
	defer pubsub.Close()

	ch := pubsub.Channel()
	for msg := range ch {
		// 包装消息并广播
		wsMsg := map[string]interface{}{
			"channel": msg.Channel,
			"data":    json.RawMessage(msg.Payload),
			"time":    time.Now().UnixMilli(),
		}
		data, _ := json.Marshal(wsMsg)
		h.broadcast <- data
	}
}

func (h *Hub) GetClientCount() int {
	h.mu.RLock()
	defer h.mu.RUnlock()
	return len(h.clients)
}
