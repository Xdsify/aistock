import { useEffect, useRef, useCallback } from 'react';
import { useMarketStore } from '../stores/marketStore';
import { usePositionStore } from '../stores/positionStore';
import { useSignalStore } from '../stores/signalStore';
import { useConnectionStore } from '../stores/connectionStore';
import { useToastStore } from '../stores/toastStore';

type MessageHandler = (channel: string, data: any) => void;

export function useWebSocket() {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number>(undefined);
  const updateQuote = useMarketStore((s) => s.updateQuote);
  const updateSentiment = useMarketStore((s) => s.updateSentiment);
  const updatePosition = usePositionStore((s) => s.updatePosition);
  const addSignal = useSignalStore((s) => s.addSignal);
  const setConnected = useConnectionStore((s) => s.setConnected);
  const pushToast = useToastStore((s) => s.push);

  const connect = useCallback(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.hostname}:8081/ws`;

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      console.log('WebSocket已连接');
      setConnected(true);
      // 订阅所有频道
      ws.send(JSON.stringify({ type: 'subscribe', channel: 'market:quote' }));
      ws.send(JSON.stringify({ type: 'subscribe', channel: 'order:update' }));
      ws.send(JSON.stringify({ type: 'subscribe', channel: 'position:update' }));
      ws.send(JSON.stringify({ type: 'subscribe', channel: 'signal:new' }));
      ws.send(JSON.stringify({ type: 'subscribe', channel: 'risk:alert' }));
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        handleMessage(msg.channel, msg.data);
      } catch (e) {
        console.error('消息解析失败:', e);
      }
    };

    ws.onclose = () => {
      console.log('WebSocket断开, 5秒后重连');
      setConnected(false);
      reconnectTimeoutRef.current = window.setTimeout(connect, 5000);
    };

    ws.onerror = (err) => {
      console.error('WebSocket错误:', err);
      setConnected(false);
      ws.close();
    };
  }, []);

  const handleMessage: MessageHandler = (channel, data) => {
    switch (channel) {
      case 'market:quote':
        updateQuote(data);
        break;
      case 'market:sentiment':
        updateSentiment(data);
        break;
      case 'position:update':
        updatePosition(data);
        break;
      case 'signal:new':
        addSignal(data);
        break;
      case 'risk:alert':
        pushToast(data?.level === 'CRITICAL' ? 'error' : 'warning', `风控告警: ${data?.message || JSON.stringify(data)}`);
        break;
    }
  };

  useEffect(() => {
    connect();
    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      wsRef.current?.close();
    };
  }, [connect]);

  return { ws: wsRef.current };
}
