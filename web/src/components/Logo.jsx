import { Link } from 'react-router-dom'

export default function Logo() {
  return (
    <Link to="/" className="kp-logo" aria-label="Kindred Path2College home">
      <span className="kp-logo-mark">K</span>
      <span>
        Kindred<span style={{ color: '#8b5cf6' }}> · Path2College</span>
      </span>
    </Link>
  )
}
