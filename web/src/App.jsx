import { Routes, Route, useLocation, useNavigate, NavLink } from 'react-router-dom'
import { Layout, Menu, Button, Grid, Drawer } from 'antd'
import { MenuOutlined, MessageOutlined } from '@ant-design/icons'
import { useState } from 'react'
import Logo from './components/Logo.jsx'
import Home from './pages/Home.jsx'
import CollegePrep from './pages/CollegePrep.jsx'
import FinancialAid from './pages/FinancialAid.jsx'
import Scholarships from './pages/Scholarships.jsx'
import CollegeExplorer from './pages/CollegeExplorer.jsx'
import Advisor from './pages/Advisor.jsx'

const { Header, Content, Footer } = Layout
const { useBreakpoint } = Grid

const NAV = [
  { key: '/college-prep', label: 'College Prep' },
  { key: '/financial-aid', label: 'Financial Aid' },
  { key: '/scholarships', label: 'Scholarships' },
  { key: '/colleges', label: 'College Explorer' },
]

export default function App() {
  const loc = useLocation()
  const navigate = useNavigate()
  const screens = useBreakpoint()
  const [drawer, setDrawer] = useState(false)
  const selected = '/' + (loc.pathname.split('/')[1] || '')

  const goto = (key) => {
    navigate(key)
    setDrawer(false)
  }

  return (
    <Layout style={{ minHeight: '100vh', background: 'transparent' }}>
      <Header
        style={{
          position: 'sticky',
          top: 0,
          zIndex: 20,
          background: 'rgba(255,255,255,0.92)',
          backdropFilter: 'blur(8px)',
          borderBottom: '1px solid #eee7fb',
          display: 'flex',
          alignItems: 'center',
          gap: 24,
          padding: '0 24px',
          height: 66,
        }}
      >
        <Logo />
        {screens.md ? (
          <>
            <Menu
              mode="horizontal"
              selectedKeys={[selected]}
              onClick={(e) => goto(e.key)}
              items={NAV}
              style={{ flex: 1, border: 'none', background: 'transparent', fontWeight: 600 }}
            />
            <Button type="primary" icon={<MessageOutlined />} onClick={() => goto('/advisor')}>
              Talk to an advisor
            </Button>
          </>
        ) : (
          <>
            <div style={{ flex: 1 }} />
            <Button type="text" icon={<MenuOutlined />} onClick={() => setDrawer(true)} />
          </>
        )}
      </Header>

      <Drawer open={drawer} onClose={() => setDrawer(false)} title="Menu" width={280}>
        <Menu
          mode="inline"
          selectedKeys={[selected]}
          onClick={(e) => goto(e.key)}
          items={[...NAV, { type: 'divider' }, { key: '/advisor', label: 'Talk to an advisor' }]}
        />
      </Drawer>

      <Content>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/college-prep" element={<CollegePrep />} />
          <Route path="/financial-aid" element={<FinancialAid />} />
          <Route path="/scholarships" element={<Scholarships />} />
          <Route path="/colleges" element={<CollegeExplorer />} />
          <Route path="/advisor" element={<Advisor />} />
          <Route path="*" element={<Home />} />
        </Routes>
      </Content>

      <Footer className="kp-footer">
        <div className="kp-container" style={{ display: 'flex', flexWrap: 'wrap', gap: 24, justifyContent: 'space-between' }}>
          <div style={{ maxWidth: 420 }}>
            <strong style={{ color: '#fff', fontFamily: 'Sora' }}>Kindred · Path2College</strong>
            <p style={{ marginTop: 8 }}>
              A free guide to college for first-generation and low-income students.
              Built as a capstone project. Not affiliated with any college or the U.S. Department of Education.
            </p>
          </div>
          <div style={{ display: 'flex', gap: 40 }}>
            <div>
              <div style={{ color: '#fff', fontWeight: 700, marginBottom: 8 }}>Explore</div>
              {NAV.map((n) => (
                <div key={n.key}>
                  <NavLink to={n.key} style={{ color: '#d8ccff' }}>{n.label}</NavLink>
                </div>
              ))}
            </div>
            <div>
              <div style={{ color: '#fff', fontWeight: 700, marginBottom: 8 }}>Official</div>
              <div><a href="https://studentaid.gov" target="_blank" rel="noopener">studentaid.gov</a></div>
              <div><a href="https://www.commonapp.org" target="_blank" rel="noopener">Common App</a></div>
              <div><a href="https://collegescorecard.ed.gov" target="_blank" rel="noopener">College Scorecard</a></div>
            </div>
          </div>
        </div>
      </Footer>
    </Layout>
  )
}
