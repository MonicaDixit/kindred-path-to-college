import { useEffect, useState } from 'react'
import { Typography, Timeline, Card, Spin, Alert, List } from 'antd'
import { CheckCircleTwoTone } from '@ant-design/icons'
import PageHeader from '../components/PageHeader.jsx'
import LinkGrid from '../components/LinkGrid.jsx'
import { api } from '../lib/api.js'

const { Title, Paragraph } = Typography

export default function CollegePrep() {
  const [data, setData] = useState(null)
  const [err, setErr] = useState(null)

  useEffect(() => {
    api.resources().then((r) => setData(r.college_prep)).catch((e) => setErr(e.message))
  }, [])

  if (err) return <div className="kp-container kp-section"><Alert type="error" message={err} /></div>
  if (!data) return <div className="kp-container kp-section"><Spin /></div>

  return (
    <>
      <PageHeader eyebrow="College Prep" title={data.title} tagline={data.tagline} />
      <section className="kp-section">
        <div className="kp-container">
          <Paragraph style={{ fontSize: 17, maxWidth: 720 }}>{data.intro}</Paragraph>

          <Title level={3} style={{ marginTop: 40 }}>Your timeline</Title>
          <Timeline
            style={{ marginTop: 20 }}
            items={data.timeline.map((phase) => ({
              color: '#6d28d9',
              children: (
                <Card
                  size="small"
                  className="kp-pathcard"
                  styles={{ body: { padding: 16 } }}
                  style={{ maxWidth: 640 }}
                >
                  <Title level={5} style={{ marginTop: 0 }}>{phase.phase}</Title>
                  <List
                    size="small"
                    dataSource={phase.tasks}
                    renderItem={(t) => (
                      <List.Item style={{ border: 'none', padding: '4px 0' }}>
                        <CheckCircleTwoTone twoToneColor="#6d28d9" style={{ marginRight: 8 }} />
                        {t}
                      </List.Item>
                    )}
                  />
                </Card>
              ),
            }))}
          />

          <Title level={3} style={{ marginTop: 40 }}>Tools &amp; official links</Title>
          <div style={{ marginTop: 16 }}>
            <LinkGrid links={data.links} />
          </div>
        </div>
      </section>
    </>
  )
}
