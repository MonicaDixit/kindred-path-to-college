import { useEffect, useRef, useState, useCallback } from 'react'
import { useLocation } from 'react-router-dom'
import {
  Row, Col, Card, Input, Button, Typography, Tag, Space, Avatar, Alert, App,
} from 'antd'
import {
  SendOutlined, CompassOutlined, EditOutlined, CalendarOutlined,
  PlusOutlined, HeartFilled,
} from '@ant-design/icons'
import Markdown from '../components/Markdown.jsx'
import SessionSidebar from '../components/SessionSidebar.jsx'
import { api } from '../lib/api.js'
import { getSessionId, resetSessionId } from '../lib/session.js'

const { Title, Text, Paragraph } = Typography

const AGENT_ICON = {
  discovery: <CompassOutlined />,
  essay: <EditOutlined />,
  planning: <CalendarOutlined />,
  coordinator: <HeartFilled />,
  support: <HeartFilled />,
}
const AGENT_COLOR = {
  discovery: '#6d28d9', essay: '#be185d', planning: '#0e7490',
  coordinator: '#6d28d9', support: '#6d28d9',
}
// Intents where a routing tag would feel cold / clinical - hide it.
const HIDE_INTENT_TAG = new Set(['crisis', 'emotional_support', 'help'])

const SUGGESTIONS = [
  "I'm pre-med, 3.2 GPA, 1280 SAT, first-gen. Give me colleges.",
  'Tell me about the University of Washington. What is the deadline?',
  'How should I approach a first-gen identity essay?',
  "What's my deadline order? Help me plan my weeks.",
]

// Shown when the student arrived from a specific agent tile - examples for that
// specialist, so they know what to ask. Nothing is ever sent automatically.
const AGENT_SUGGESTIONS = {
  discovery: [
    "I'm pre-med, 3.2 GPA, 1280 SAT, first-gen. Give me colleges.",
    'Tell me about the University of Washington. What are my chances?',
    'Which of my schools is the best fit for me?',
  ],
  essay: [
    'How should I approach a first-gen identity essay?',
    "Here's my draft — can you give me feedback? ...",
    'Is my opening too cliche?',
  ],
  planning: [
    "What's my deadline order?",
    'Help me plan my weeks.',
    'Which application should I start first?',
  ],
}

export default function Advisor() {
  const { message: toast } = App.useApp()
  const loc = useLocation()
  const [sessionId, setSessionId] = useState(getSessionId())
  const [messages, setMessages] = useState([])
  const [state, setState] = useState({})
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const scrollRef = useRef(null)
  const inputRef = useRef(null)
  const revealTimer = useRef(null)

  // Suggestions to show in the empty state - agent-specific if the student came
  // from an agent tile, or a caller-supplied list (e.g. College Explorer).
  const suggestions =
    loc.state?.suggestions ||
    AGENT_SUGGESTIONS[loc.state?.agent] ||
    SUGGESTIONS

  const pickSuggestion = (s) => {
    setInput(s)
    requestAnimationFrame(() => inputRef.current?.focus())
  }

  const scrollDown = () => {
    requestAnimationFrame(() => {
      const el = scrollRef.current
      if (el) el.scrollTop = el.scrollHeight
    })
  }

  // Bring the TOP of the newest advisor reply to the top of the scroll area, so
  // the student starts reading from the first line instead of being dumped at
  // the end of a long answer.
  const anchorLastAnswer = () => {
    // two frames: let React commit the new bubble, then measure & scroll
    requestAnimationFrame(() => requestAnimationFrame(() => {
      const el = scrollRef.current
      if (!el) return
      const nodes = el.querySelectorAll('.kp-msg-agent')
      const last = nodes[nodes.length - 1]
      if (!last) return
      const top =
        last.getBoundingClientRect().top -
        el.getBoundingClientRect().top +
        el.scrollTop -
        12
      el.scrollTo({ top, behavior: 'smooth' })
    }))
  }

  const stopReveal = () => {
    if (revealTimer.current) {
      clearInterval(revealTimer.current)
      revealTimer.current = null
    }
  }

  // Snap any in-progress reveal to its full text immediately.
  const finalizeReveal = () => {
    stopReveal()
    setMessages((m) =>
      m.map((x) => (x.revealing ? { ...x, content: x.full, revealing: false } : x)),
    )
  }

  // Progressively unveil an already-received reply, word by word, so it reads
  // like the advisor is typing rather than a wall of text appearing at once.
  const startReveal = (full) => {
    stopReveal()
    const tokens = (full || '').split(/(\s+)/) // keep whitespace so joins are exact
    const reduceMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
    if (tokens.length <= 1 || reduceMotion) {
      finalizeReveal()
      return
    }
    const step = Math.max(2, Math.ceil(tokens.length / 90)) // ~90 ticks, whatever the length
    let shown = 0
    revealTimer.current = setInterval(() => {
      shown += step
      setMessages((m) => {
        if (!m.length) return m
        const last = m[m.length - 1]
        if (!last || !last.revealing) {
          stopReveal()
          return m
        }
        const copy = m.slice()
        if (shown >= tokens.length) {
          copy[copy.length - 1] = { ...last, content: last.full, revealing: false }
          stopReveal()
        } else {
          copy[copy.length - 1] = { ...last, content: tokens.slice(0, shown).join('') }
        }
        return copy
      })
    }, 30)
  }

  useEffect(() => stopReveal, [])

  const send = useCallback(
    async (text) => {
      const msg = (text ?? input).trim()
      if (!msg || busy) return
      finalizeReveal() // if a previous reply is still unveiling, complete it now
      setInput('')
      setError(null)
      setMessages((m) => [...m, { role: 'user', content: msg }])
      setBusy(true)
      scrollDown()
      try {
        const res = await api.chat(sessionId, msg)
        const full = res.reply || ''
        setMessages((m) => [
          ...m,
          {
            role: 'assistant',
            content: '',
            full,
            revealing: full.length > 0,
            agent: res.agent,
            intent: res.intent,
            escalated: res.escalated,
            awaitingResume: res.awaiting_resume,
          },
        ])
        setState(res.state || {})
        anchorLastAnswer()
        startReveal(full)
      } catch (e) {
        setError(e.message || 'Something went wrong. Is the API server running on port 8000?')
        setMessages((m) => [
          ...m,
          { role: 'assistant', content: null, failed: true },
        ])
        scrollDown()
      } finally {
        setBusy(false)
      }
    },
    [input, busy, sessionId],
  )

  // load existing session history
  useEffect(() => {
    api
      .session(sessionId)
      .then((data) => {
        if (data.messages?.length) setMessages(data.messages.map((m) => ({ ...m })))
        setState(data.state || {})
        scrollDown()
      })
      .catch(() => {})
  }, [sessionId])

  const newConversation = () => {
    stopReveal()
    const id = resetSessionId()
    setSessionId(id)
    setMessages([])
    setState({})
    setError(null)
    setInput('')
    toast.success('Started a fresh conversation')
  }

  return (
    <section style={{ background: '#faf9ff' }}>
      <div className="kp-container" style={{ padding: '28px 24px 48px' }}>
        <Row justify="space-between" align="middle" style={{ marginBottom: 16 }}>
          <Col>
            <Title level={2} style={{ margin: 0 }}>Your advisors</Title>
            <Text type="secondary">
              Ask anything about applying to college. Kindred routes you to the right specialist.
            </Text>
          </Col>
          <Col>
            <Button icon={<PlusOutlined />} onClick={newConversation}>New conversation</Button>
          </Col>
        </Row>

        <Row gutter={[20, 20]}>
          <Col xs={24} lg={16}>
            <Card
              styles={{
                body: {
                  padding: 0,
                  height: '100%',
                  display: 'flex',
                  flexDirection: 'column',
                  minHeight: 0,
                },
              }}
              style={{ height: '72vh', minHeight: 520, overflow: 'hidden' }}
            >
              <div ref={scrollRef} className="kp-chat-scroll">
                {messages.length === 0 && !busy && (
                  <div style={{ margin: 'auto', textAlign: 'center', maxWidth: 460 }}>
                    <Avatar size={56} style={{ background: '#6d28d9' }} icon={<HeartFilled />} />
                    <Title level={4} style={{ marginTop: 16 }}>Hi, I&apos;m Kindred.</Title>
                    <Paragraph type="secondary">
                      Type a message below to get started. Not sure what to ask?
                      Tap a suggestion to drop it in the box — you can edit it before sending.
                    </Paragraph>
                    <Space direction="vertical" style={{ width: '100%' }}>
                      {suggestions.map((s) => (
                        <Button
                          key={s}
                          block
                          style={{ whiteSpace: 'normal', height: 'auto', padding: '10px 14px', textAlign: 'left' }}
                          onClick={() => pickSuggestion(s)}
                        >
                          {s}
                        </Button>
                      ))}
                    </Space>
                  </div>
                )}

                {messages.map((m, i) =>
                  m.role === 'user' ? (
                    <div key={i} className="kp-msg kp-msg-user">{m.content}</div>
                  ) : (
                    <div key={i} className="kp-msg kp-msg-agent">
                      {m.failed ? (
                        <Text type="danger">Couldn&apos;t reach the advisor. Try again.</Text>
                      ) : (
                        <>
                          <Space style={{ marginBottom: 8 }}>
                            <Avatar
                              size={22}
                              style={{ background: AGENT_COLOR[m.agent?.id] || '#6d28d9' }}
                              icon={AGENT_ICON[m.agent?.id] || <HeartFilled />}
                            />
                            <Text strong>{m.agent?.name || 'Kindred'}</Text>
                            {m.intent && !HIDE_INTENT_TAG.has(m.intent) && (
                              <Tag bordered={false} color="purple">{m.intent.replace(/_/g, ' ')}</Tag>
                            )}
                          </Space>
                          <Markdown>{m.content}</Markdown>
                          {m.escalated && (
                            <Alert
                              type="info"
                              showIcon
                              style={{ marginTop: 10 }}
                              message="Flagged for a human advisor"
                              description="A Kindred advisor will review this and follow up. Say “connect me with an advisor” if you'd like to talk to someone directly."
                            />
                          )}
                        </>
                      )}
                    </div>
                  ),
                )}

                {busy && (
                  <div className="kp-msg kp-msg-agent">
                    <Text type="secondary">Thinking…</Text>
                  </div>
                )}
              </div>

              {error && (
                <Alert type="error" showIcon banner message={error} style={{ margin: 0, flexShrink: 0 }} />
              )}
              {state.awaiting_resume && (
                <Alert
                  type="warning"
                  banner
                  showIcon={false}
                  style={{ margin: 0, flexShrink: 0 }}
                  message="Take your time. When you're ready to pick things back up, just say so — there's no rush."
                />
              )}

              <div style={{ borderTop: '1px solid #eee7fb', padding: 14, background: '#fff', flexShrink: 0 }}>
                <Space.Compact style={{ width: '100%' }}>
                  <Input.TextArea
                    ref={inputRef}
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    placeholder={state.awaiting_resume
                      ? 'Type when you’re ready…'
                      : 'Ask about colleges, essays, aid, or deadlines…'}
                    autoSize={{ minRows: 1, maxRows: 4 }}
                    onPressEnter={(e) => {
                      if (!e.shiftKey) {
                        e.preventDefault()
                        send()
                      }
                    }}
                  />
                  <Button type="primary" icon={<SendOutlined />} onClick={() => send()} loading={busy} style={{ height: 'auto' }}>
                    Send
                  </Button>
                </Space.Compact>
                <Text type="secondary" style={{ fontSize: 12 }}>
                  Enter to send · Shift+Enter for a new line
                </Text>
              </div>
            </Card>
          </Col>

          <Col xs={24} lg={8}>
            <SessionSidebar state={state} />
          </Col>
        </Row>
      </div>
    </section>
  )
}
