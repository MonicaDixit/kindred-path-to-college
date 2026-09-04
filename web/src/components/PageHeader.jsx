import { Typography } from 'antd'

const { Title, Paragraph } = Typography

export default function PageHeader({ eyebrow, title, tagline, children }) {
  return (
    <div className="kp-hero" style={{ padding: '56px 0 64px' }}>
      <div className="kp-container">
        {eyebrow && <div className="kp-eyebrow">{eyebrow}</div>}
        <Title style={{ marginTop: 10 }}>{title}</Title>
        {tagline && (
          <Paragraph className="lede" style={{ marginBottom: 0 }}>
            {tagline}
          </Paragraph>
        )}
        {children}
      </div>
    </div>
  )
}
