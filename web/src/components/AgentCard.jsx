import { Card, Tag, Typography } from 'antd'
import { useNavigate } from 'react-router-dom'
import { CompassOutlined, EditOutlined, CalendarOutlined, ArrowRightOutlined } from '@ant-design/icons'

const { Title, Paragraph, Text } = Typography

const ICONS = {
  discovery: <CompassOutlined />,
  essay: <EditOutlined />,
  planning: <CalendarOutlined />,
}

export default function AgentCard({ agent }) {
  const navigate = useNavigate()
  return (
    <Card
      className="kp-pathcard"
      hoverable
      styles={{ body: { padding: 24 } }}
      style={{ cursor: 'pointer', height: '100%' }}
      onClick={() => navigate('/advisor', { state: { agent: agent.id } })}
    >
      <div className="kp-pathicon">{ICONS[agent.id] || <CompassOutlined />}</div>
      <Title level={4} style={{ margin: '0 0 4px' }}>
        {agent.name}
      </Title>
      <Tag color={agent.kind === 'Deterministic' ? 'green' : 'purple'}>{agent.kind}</Tag>
      <Paragraph style={{ marginTop: 12, minHeight: 66 }}>{agent.blurb}</Paragraph>
      {agent.examples?.[0] && (
        <Text type="secondary" italic style={{ display: 'block', marginBottom: 14 }}>
          e.g. “{agent.examples[0]}”
        </Text>
      )}
      <div style={{ color: '#6d28d9', fontWeight: 700 }}>
        Chat with {agent.name.split(' ')[0]} <ArrowRightOutlined />
      </div>
    </Card>
  )
}
