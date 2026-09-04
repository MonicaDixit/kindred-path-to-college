import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Row, Col, Card, Button, Typography, Space } from 'antd'
import {
  RocketOutlined, DollarOutlined, TrophyOutlined, BankOutlined,
  ArrowRightOutlined, HeartFilled,
} from '@ant-design/icons'
import AgentCard from '../components/AgentCard.jsx'
import { api } from '../lib/api.js'

const { Title, Paragraph, Text } = Typography

const PATHS = [
  { to: '/college-prep', icon: <RocketOutlined />, title: 'College Prep', desc: 'A step-by-step timeline from junior year to decision day, plus test prep and application tools.' },
  { to: '/financial-aid', icon: <DollarOutlined />, title: 'Financial Aid', desc: 'The FAFSA, the CSS Profile, and how to read an award letter. The sticker price is rarely what you pay.' },
  { to: '/scholarships', icon: <TrophyOutlined />, title: 'Scholarships', desc: 'National programs and search tools that prioritize first-generation and low-income students.' },
  { to: '/colleges', icon: <BankOutlined />, title: 'College Explorer', desc: 'Compare colleges by cost, aid, selectivity, and first-gen support — then ask an advisor about any of them.' },
]

const STATS = [
  { n: '$0', label: 'to use everything here' },
  { n: '~1 hr', label: 'to file the FAFSA' },
  { n: '3', label: 'AI advisors, available anytime' },
  { n: '70+', label: 'colleges that meet full need' },
]

export default function Home() {
  const navigate = useNavigate()
  const [agents, setAgents] = useState([])

  useEffect(() => {
    api.agents().then(setAgents).catch(() => {})
  }, [])

  return (
    <>
      <section className="kp-hero">
        <div className="kp-container" style={{ padding: '84px 0 92px' }}>
          <Row gutter={[48, 32]} align="middle">
            <Col xs={24} md={14}>
              <div className="kp-eyebrow">
                <HeartFilled /> For first-generation students
              </div>
              <h1 style={{ marginTop: 14 }}>
                You&apos;re the first in your family to do this. You don&apos;t have to figure it out alone.
              </h1>
              <p className="lede">
                Kindred walks you through choosing colleges, paying for them, and writing
                the essays — with free resources and advisors you can talk to whenever you&apos;re stuck.
              </p>
              <Space size="middle" wrap style={{ marginTop: 28 }}>
                <Button type="primary" size="large" icon={<ArrowRightOutlined />} onClick={() => navigate('/advisor')}>
                  Talk to an advisor
                </Button>
                <Button
                  size="large"
                  ghost
                  style={{ borderColor: 'rgba(255,255,255,0.5)', color: '#fff' }}
                  onClick={() => navigate('/college-prep')}
                >
                  Start with the basics
                </Button>
              </Space>
            </Col>
            <Col xs={24} md={10}>
              <Card
                style={{ background: 'rgba(255,255,255,0.08)', borderColor: 'rgba(255,255,255,0.18)' }}
                styles={{ body: { padding: 22 } }}
              >
                <Text style={{ color: '#fbbf24', fontWeight: 700, letterSpacing: '0.1em', fontSize: 12 }}>
                  WHERE TO BEGIN
                </Text>
                <div style={{ marginTop: 12, display: 'flex', flexDirection: 'column', gap: 10 }}>
                  {['Not sure where to apply? → College Explorer',
                    'Worried about cost? → Financial Aid',
                    'Essay due soon? → Essay Coach',
                    'Deadlines piling up? → Planning Assistant'].map((t) => (
                    <div key={t} style={{ color: '#efeaff' }}>{t}</div>
                  ))}
                </div>
              </Card>
            </Col>
          </Row>
        </div>
      </section>

      <section className="kp-section">
        <div className="kp-container">
          <Title level={2}>Four things to work through</Title>
          <Paragraph type="secondary" style={{ fontSize: 16, maxWidth: 620 }}>
            Take them in any order. Each section is short, plain-language, and links straight to the
            official forms and tools.
          </Paragraph>
          <Row gutter={[20, 20]} style={{ marginTop: 24 }}>
            {PATHS.map((p) => (
              <Col xs={24} sm={12} lg={6} key={p.to}>
                <Link to={p.to}>
                  <Card className="kp-pathcard" styles={{ body: { padding: 22 } }}>
                    <div className="kp-pathicon">{p.icon}</div>
                    <Title level={4} style={{ margin: '0 0 6px' }}>{p.title}</Title>
                    <Text type="secondary">{p.desc}</Text>
                    <div style={{ marginTop: 14, color: '#6d28d9', fontWeight: 700 }}>
                      Open <ArrowRightOutlined />
                    </div>
                  </Card>
                </Link>
              </Col>
            ))}
          </Row>
        </div>
      </section>

      <section className="kp-section-tight kp-band">
        <div className="kp-container">
          <Row gutter={[24, 24]}>
            {STATS.map((s) => (
              <Col xs={12} md={6} key={s.label} style={{ textAlign: 'center' }}>
                <div style={{ fontFamily: 'Sora', fontWeight: 800, fontSize: 34, color: '#fbbf24' }}>
                  {s.n}
                </div>
                <Text style={{ color: '#d8ccff' }}>{s.label}</Text>
              </Col>
            ))}
          </Row>
        </div>
      </section>

      <section className="kp-section">
        <div className="kp-container">
          <Title level={2}>Meet your advisors</Title>
          <Paragraph type="secondary" style={{ fontSize: 16, maxWidth: 640 }}>
            Three specialists share what you tell them, so you never repeat yourself. Ask a question
            in plain English — Kindred sends it to the right one. Pick a specialist to start, or
            just <a onClick={() => navigate('/advisor')}>open the chat</a>.
          </Paragraph>
          <Row gutter={[20, 20]} style={{ marginTop: 24 }}>
            {agents.map((a) => (
              <Col xs={24} md={8} key={a.id}>
                <AgentCard agent={a} />
              </Col>
            ))}
          </Row>
        </div>
      </section>
    </>
  )
}
