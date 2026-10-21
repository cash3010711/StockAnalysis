import React from 'react'

interface DisclaimerProps {
  customText?: string
}

export const Disclaimer: React.FC<DisclaimerProps> = ({
  customText = '僅供個人研究參考，非投資建議',
}) => {
  return (
    <footer
      style={{
        marginTop: '32px',
        padding: '16px',
        background: '#f8fafc',
        borderTop: '1px solid #e2e8f0',
        textAlign: 'center',
        color: '#64748b',
        fontSize: '13px',
      }}
      data-testid="disclaimer"
    >
      <p style={{ margin: 0 }}>⚠️ {customText}</p>
    </footer>
  )
}
