// "Bold and encouraging" — Ant Design theme tokens.
export const BRAND = {
  violet: '#6D28D9',
  violetDark: '#4C1D95',
  indigo: '#4338CA',
  gold: '#FBBF24',
  ink: '#1E1B2E',
  cloud: '#F6F4FF',
}

export const theme = {
  token: {
    colorPrimary: BRAND.violet,
    colorInfo: BRAND.violet,
    colorSuccess: '#16A34A',
    colorWarning: '#D97706',
    colorTextBase: BRAND.ink,
    borderRadius: 12,
    fontFamily:
      "'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
    fontSize: 15,
    lineHeight: 1.65,
    controlHeight: 40,
    wireframe: false,
  },
  components: {
    Button: { fontWeight: 700, primaryShadow: '0 6px 18px rgba(109,40,217,0.28)' },
    Card: { borderRadiusLG: 18 },
    Typography: { titleMarginBottom: '0.4em', titleMarginTop: '1em' },
    Tag: { borderRadiusSM: 999 },
    Segmented: { itemSelectedBg: BRAND.violet, itemSelectedColor: '#fff' },
  },
}
