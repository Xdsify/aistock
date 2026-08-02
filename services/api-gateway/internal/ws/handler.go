package ws

import (
	"encoding/json"
	"log"
	"time"

	"github.com/gofiber/contrib/websocket"
	"github.com/redis/go-redis/v9"
)

// HandleConnection 处理单个WebSocket连接
func HandleConnection(c *websocket.Conn, hub *Hub, rdb *redis.Client) {
	client := &Client{
		Conn:     c,
		Send:     make(chan []byte, 256),
		UserID:   "anonymous",
		Channels: make(map[string]bool),
	}

	hub.register <- client

	// 发送欢迎消息
	welcome, _ := json.Marshal(map[string]interface{}{
		"type":    "connected",
		"message": "已连接到AI炒股实时数据服务",
		"time":    time.Now().UnixMilli(),
	})
	client.Send <- welcome

	defer func() {
		hub.unregister <- client
		c.Close()
	}()

	// 启动写协程
	go writePump(client)

	// 读循环 (处理客户端消息)
	for {
		_, message, err := c.ReadMessage()
		if err != nil {
			if websocket.IsUnexpectedCloseError(err,
				websocket.CloseGoingAway, websocket.CloseNormalClosure) {
				log.Printf("WebSocket错误: %v", err)
			}
			break
		}

		// 处理客户端消息
		var msg map[string]interface{}
		if err := json.Unmarshal(message, &msg); err != nil {
			continue
		}

		msgType, _ := msg["type"].(string)
		switch msgType {
		case "subscribe":
			// 订阅特定频道
			channel, _ := msg["channel"].(string)
			if channel != "" {
				client.Channels[channel] = true
			}
		case "unsubscribe":
			channel, _ := msg["channel"].(string)
			delete(client.Channels, channel)
		case "ping":
			client.Send <- []byte(`{"type":"pong"}`)
		}
	}
}

func writePump(client *Client) {
	ticker := time.NewTicker(30 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case message, ok := <-client.Send:
			if !ok {
				client.Conn.WriteMessage(websocket.CloseMessage, []byte{})
				return
			}
			if err := client.Conn.WriteMessage(websocket.TextMessage, message); err != nil {
				return
			}
		case <-ticker.C:
			// 心跳
			ping := []byte(`{"type":"heartbeat"}`)
			if err := client.Conn.WriteMessage(websocket.TextMessage, ping); err != nil {
				return
			}
		}
	}
}
