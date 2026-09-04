import { useEffect, useState } from 'react'
import { Typography, Card, Spin, Alert, Row, Col, Tag, List, Button } from 'antd'
import { ExportOutlined, BulbOutlined } from '@ant-design/icons'
import PageHeader from '../components/PageHeader.jsx'
import LinkGrid from '../components/LinkGrid.jsx'
import { api } from '../lib/api.js'

const { Title, Paragraph, Text } = Typography

export default function Scholarships() {
  const [data, setData] = useState(null)
  const [err, setErr] = useState(null)

  useEffect(() => {
    api.resources().then((r) => setData(r.scholarships)).catch((e) => setErr(e.message))
  }, [])

  if (err) return <div className="kp-container kp-section"><Alert type="error" message={err} /></div>
  if (!data) return <div className="kp-container kp-section"><Spin /></div>

  return (
    <>
      <PageHeader eyebrow="Scholarships" title={data.title} tagline={data.tagline} />
      <section className="kp-section">
        <div className="kp-container">
          <Paragraph style={{ fontSize: 17, maxWidth: 720 }}>{data.intro}</Paragraph>

          <Card
            className="kp-pathcard"
            style={{ marginTop: 24, background: '#f6f4ff', borderColor: '#e3d9ff' }}
            styles={{ body: { padding: 20 } }}
          >
            <Title level={5} style={{ marginTop: 0 }}>
              <BulbOutlined style={{ color: '#d97706', marginRight: 8 }} />
              How to actually win them
            </Title>
            <List
              size="small"
              dataSource={data.tips}
              renderItem={(t) => (
                <List.Item style={{ border: 'none', padding: '5px 0' }}>• {t}</List.Item>
              )}
            />
          </Card>

          <Title level={3} style={{ marginTop: 40 }}>National programs</Title>
          <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
            {data.programs.map((p) => (
              <Col xs={24} md={12} key={p.name}>
                <Card className="kp-pathcard" styles={{ body: { padding: 20 } }} style={{ height: '100%' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
                    <Text strong style={{ fontSize: 16 }}>{p.name}</Text>
                  </div>
                  <div style={{ margin: '10px 0' }}>
                    <Tag color="purple">{p.focus}</Tag>
                  </div>
                  <Paragraph style={{ marginBottom: 4 }}>
                    <Text type="secondary">Award:</Text> <Text strong>{p.award}</Text>
                  </Paragraph>
                  <Paragraph style={{ marginBottom: 12 }}>
                    <Text type="secondary">Typical deadline:</Text> {p.deadline}
                  </Paragraph>
                  <Button
                    size="small"
                    icon={<ExportOutlined />}
                    onClick={() => window.open(p.url, '_blank', 'noopener')}
                  >
                    Program site
                  </Button>
                </Card>
              </Col>
            ))}
          </Row>

          <Title level={3} style={{ marginTop: 40 }}>Free search tools</Title>
          <div style={{ marginTop: 16 }}>
            <LinkGrid links={data.links} />
          </div>
        </div>
      </section>
    </>
  )
}
