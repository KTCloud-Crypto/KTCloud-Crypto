import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  ArrowLeft,
  BadgeCheck,
  Eye,
  EyeOff,
  KeyRound,
  LockKeyhole,
  ShieldCheck,
  TrendingUp,
  UserRound,
  WalletCards,
} from 'lucide-react'
import { apiFetch } from '../api/client'
import styles from './SignupPage.module.css'

const initialForm = {
  userId: '',
  password: '',
  passwordConfirm: '',
  accessKey: '',
  secretKey: '',
  nickname: '',
  agree: false,
}

export default function SignupPage() {
  const navigate = useNavigate()
  const [form, setForm] = useState(initialForm)
  const [submitted, setSubmitted] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [formError, setFormError] = useState('')
  const [visible, setVisible] = useState({
    password: false,
    passwordConfirm: false,
    accessKey: false,
    secretKey: false,
  })

  const errors = useMemo(() => {
    const nextErrors = {}

    if (!/^[a-zA-Z0-9_]{4,20}$/.test(form.userId)) {
      nextErrors.userId = '영문, 숫자, 밑줄을 사용해 4~20자로 입력해 주세요.'
    }
    if (!/^(?=.*[A-Za-z])(?=.*\d).{8,32}$/.test(form.password)) {
      nextErrors.password = '영문과 숫자를 포함해 8~32자로 입력해 주세요.'
    }
    if (!form.passwordConfirm || form.password !== form.passwordConfirm) {
      nextErrors.passwordConfirm = '비밀번호가 일치하지 않습니다.'
    }
    if (form.accessKey.trim().length < 10) {
      nextErrors.accessKey = 'Upbit Access Key를 정확히 입력해 주세요.'
    }
    if (form.secretKey.trim().length < 10) {
      nextErrors.secretKey = 'Upbit Secret Key를 정확히 입력해 주세요.'
    }
    if (form.nickname.trim().length < 2 || form.nickname.trim().length > 12) {
      nextErrors.nickname = '닉네임은 2~12자로 입력해 주세요.'
    }
    if (!form.agree) {
      nextErrors.agree = '서비스 이용 및 API Key 보관 정책에 동의해 주세요.'
    }

    return nextErrors
  }, [form])

  const updateField = (event) => {
    const { name, value, checked, type } = event.target
    setForm((current) => ({
      ...current,
      [name]: type === 'checkbox' ? checked : value,
    }))
  }

  const toggleVisible = (field) => {
    setVisible((current) => ({ ...current, [field]: !current[field] }))
  }

  const handleSubmit = async (event) => {
    event.preventDefault()
    setSubmitted(true)
    setFormError('')

    if (Object.keys(errors).length > 0) return

    setIsSubmitting(true)
    try {
      const data = await apiFetch('/auth/signup', {
        method: 'POST',
        body: JSON.stringify({
          username: form.userId.trim(),
          password: form.password,
          nickname: form.nickname.trim(),
          access_key: form.accessKey.trim(),
          secret_key: form.secretKey.trim(),
        }),
      })

      navigate('/login', {
        replace: true,
        state: {
          registered: true,
          userId: data.username,
        },
      })
    } catch (error) {
      setFormError(
        error instanceof TypeError
          ? '서버에 연결할 수 없습니다. 백엔드 실행 상태와 주소를 확인해 주세요.'
          : error.message,
      )
    } finally {
      setIsSubmitting(false)
    }
  }

  const fieldError = (name) => submitted && errors[name]

  return (
    <main className={styles.shell}>
      <section className={styles.visual}>
        <div className={styles.visualInner}>
          <div className={styles.brand}>
            <span className={styles.brandMark}><TrendingUp size={24} /></span>
            <span>SignalTrade</span>
          </div>

          <div className={styles.copy}>
            <span className={styles.eyebrow}>SECURE EXCHANGE CONNECTION</span>
            <h1>안전한 자동매매를 위한<br />첫 설정을 시작하세요.</h1>
            <p>
              계정과 Upbit Open API를 연결하면 선택한 전략에 따라
              주문을 실행하고, 거래 상태와 손익을 한곳에서 관리할 수 있습니다.
            </p>
          </div>

          <div className={styles.securityCard}>
            <div className={styles.securityIcon}><ShieldCheck size={27} /></div>
            <div>
              <span>API KEY SECURITY</span>
              <strong>민감 정보는 화면에 다시 노출하지 않습니다.</strong>
              <p>Secret Key는 서버에서 암호화하여 저장하며 화면에 다시 표시하지 않습니다.</p>
            </div>
          </div>
        </div>
      </section>

      <section className={styles.panel}>
        <div className={styles.formWrap}>
          <div className={styles.topLine}>
            <div className={styles.mobileBrand}>
              <span className={styles.brandMark}><TrendingUp size={23} /></span>
              <strong>SignalTrade</strong>
            </div>
            <button className={styles.backButton} type="button" onClick={() => navigate('/login')}>
              <ArrowLeft size={16} /> 로그인으로 돌아가기
            </button>
          </div>

          <div className={styles.heading}>
            <span className={styles.eyebrowDark}>CREATE ACCOUNT</span>
            <h2>회원가입</h2>
            <p>자동매매 계정과 Upbit API 정보를 등록해 주세요.</p>
          </div>

          <form onSubmit={handleSubmit} className={styles.form} noValidate>
            <div className={styles.twoColumns}>
              <Field
                label="아이디"
                name="userId"
                value={form.userId}
                onChange={updateField}
                icon={<UserRound size={18} />}
                placeholder="예: trader_01"
                autoComplete="username"
                error={fieldError('userId')}
              />
              <Field
                label="닉네임"
                name="nickname"
                value={form.nickname}
                onChange={updateField}
                icon={<BadgeCheck size={18} />}
                placeholder="대시보드 표시 이름"
                autoComplete="nickname"
                error={fieldError('nickname')}
              />
            </div>

            <div className={styles.twoColumns}>
              <Field
                label="비밀번호"
                name="password"
                value={form.password}
                onChange={updateField}
                icon={<LockKeyhole size={18} />}
                placeholder="영문·숫자 포함 8자 이상"
                type={visible.password ? 'text' : 'password'}
                autoComplete="new-password"
                error={fieldError('password')}
                action={
                  <VisibilityButton
                    visible={visible.password}
                    onClick={() => toggleVisible('password')}
                    label="비밀번호 표시 전환"
                  />
                }
              />
              <Field
                label="비밀번호 확인"
                name="passwordConfirm"
                value={form.passwordConfirm}
                onChange={updateField}
                icon={<LockKeyhole size={18} />}
                placeholder="비밀번호 재입력"
                type={visible.passwordConfirm ? 'text' : 'password'}
                autoComplete="new-password"
                error={fieldError('passwordConfirm')}
                action={
                  <VisibilityButton
                    visible={visible.passwordConfirm}
                    onClick={() => toggleVisible('passwordConfirm')}
                    label="비밀번호 확인 표시 전환"
                  />
                }
              />
            </div>

            <div className={styles.apiSection}>
              <div className={styles.apiTitle}>
                <span><WalletCards size={17} /> Upbit Open API</span>
                <small><ShieldCheck size={14} /> 서버 암호화 저장 권장</small>
              </div>
              <button
                type="button"
                className={styles.apiKeyGuideLink}
                onClick={() => navigate('/guide/upbit-key')}
              >
                Upbit API 키가 아직 없으신가요? 발급 방법 보기 →
              </button>
              <Field
                label="Upbit Access Key"
                value={form.accessKey}
                onChange={updateField}
                icon={<KeyRound size={18} />}
                placeholder="발급받은 Access Key 입력"
                type={visible.accessKey ? 'text' : 'password'}
                autoComplete="off"
                error={fieldError('accessKey')}
                action={
                  <VisibilityButton
                    visible={visible.accessKey}
                    onClick={() => toggleVisible('accessKey')}
                    label="Access Key 표시 전환"
                  />
                }
              />

              <Field
                label="Upbit Secret Key"
                name="secretKey"
                value={form.secretKey}
                onChange={updateField}
                icon={<KeyRound size={18} />}
                placeholder="발급받은 Secret Key 입력"
                type={visible.secretKey ? 'text' : 'password'}
                autoComplete="off"
                error={fieldError('secretKey')}
                action={
                  <VisibilityButton
                    visible={visible.secretKey}
                    onClick={() => toggleVisible('secretKey')}
                    label="Secret Key 표시 전환"
                  />
                }
              />
            </div>

            <label className={`${styles.agree} ${fieldError('agree') ? styles.agreeError : ''}`}>
              <input name="agree" type="checkbox" checked={form.agree} onChange={updateField} />
              <span>
                <strong>이용약관 및 개인정보처리방침에 동의합니다.</strong>
                <small>API Key의 안전한 보관 및 자동 주문 실행에 관한 안내를 확인했습니다.</small>
              </span>
            </label>
            {fieldError('agree') && <p className={styles.agreeMessage}>{errors.agree}</p>}
            {formError && <p className={styles.formError}>{formError}</p>}

            <button className={styles.submitButton} type="submit" disabled={isSubmitting}>
              {isSubmitting ? '계정 생성 중...' : '계정 만들기'}
            </button>

            <p className={styles.loginLink}>
              이미 계정이 있으신가요? <button type="button" onClick={() => navigate('/login')}>로그인</button>
            </p>
          </form>

          <footer className={styles.footer}>
            <span>© 2026 SignalTrade</span>
          </footer>
        </div>
      </section>
    </main>
  )
}

function Field({ label, icon, action, error, ...inputProps }) {
  return (
    <label className={styles.field}>
      <span>{label}</span>
      <div className={`${styles.inputWrap} ${error ? styles.inputError : ''}`}>
        {icon}
        <input {...inputProps} />
        {action}
      </div>
      {error && <small className={styles.errorMessage}>{error}</small>}
    </label>
  )
}

function VisibilityButton({ visible, onClick, label }) {
  return (
    <button type="button" className={styles.eyeButton} onClick={onClick} aria-label={label}>
      {visible ? <EyeOff size={18} /> : <Eye size={18} />}
    </button>
  )
}
