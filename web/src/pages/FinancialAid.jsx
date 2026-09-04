import { useEffect, useState } from 'react'
import { Typography, Card, Spin, Alert, Steps, Row, Col, Tag } from 'antd'
import PageHeader from '../components/PageHeader.jsx'
import LinkGrid from '../components/LinkGrid.jsx'
import { api } from '../lib/api.js'

const { Title, Paragraph, Text } = Typography

export default function FinancialAid() {
  const [data, setData] = useState(null)
  const [err, setErr] = useState(null)

  useEffect(() => {
    api.resources().then((r) => setData(r.financial_aid)).catch((e) => setErr(e.message))
  }, [])

  if (err) return <div className="kp-container kp-section"><Alert type="error" message={err} /></div>
  if (!data) return <div className="kp-container kp-section"><Spin /></div>

  return (
    <>
      <PageHeader eyebrow="Financial Aid" title={data.title} tagline={data.tagline} />
      <section className="kp-section">
        <div className="kp-container">
          <Paragraph style={{ fontSize: 17, maxWidth: 720 }}>{data.intro}</Paragraph>

          <Title level={3} style={{ marginTop: 40 }}>How to apply for aid</Title>
          <Steps
            direction="vertical"
            current={-1}
            style={{ marginTop: 20, maxWidth: 720 }}
            items={data.steps.map((s) => ({ title: s }))}
          />

          <Title level={3} style={{ marginTop: 40 }}>Aid vocabulary</Title>
          <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
            {data.glossary.map((g) => (
              <Col xs={24} md={12} key={g.term}>
                <Card className="kp-pathcard" styles={{ body: { padding: 18 } }} style={{ height: '100%' }}>
                  <Tag color="purple" style={{ fontWeight: 700 }}>{g.term}</Tag>
                  <Paragraph style={{ marginTop: 10, marginBottom: 0 }}>
                    <Text type="secondary">{g.definition}</Text>
                  </Paragraph>
                </Card>
              </Col>
            ))}
          </Row>

          <Title level={3} style={{ marginTop: 40 }}>Official links</Title>
          <div style={{ marginTop: 16 }}>
            <LinkGrid links={data.links} />
          </div>
        </div>
      </section>
    </>
  )
}
