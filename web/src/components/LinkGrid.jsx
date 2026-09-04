import { Card, Row, Col, Typography } from 'antd'
import { ExportOutlined } from '@ant-design/icons'

const { Text } = Typography

export default function LinkGrid({ links }) {
  return (
    <Row gutter={[16, 16]}>
      {links.map((l) => (
        <Col xs={24} sm={12} lg={8} key={l.url}>
          <Card
            hoverable
            className="kp-pathcard"
            styles={{ body: { padding: 20 } }}
            onClick={() => window.open(l.url, '_blank', 'noopener')}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
              <Text strong style={{ fontSize: 16 }}>
                {l.name}
              </Text>
              <ExportOutlined style={{ color: '#8b5cf6' }} />
            </div>
            {l.note && (
              <Text type="secondary" style={{ display: 'block', marginTop: 6 }}>
                {l.note}
              </Text>
            )}
          </Card>
        </Col>
      ))}
    </Row>
  )
}
