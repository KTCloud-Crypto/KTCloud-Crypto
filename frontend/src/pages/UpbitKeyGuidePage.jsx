import { useNavigate } from 'react-router-dom'
import { ArrowLeft, CheckCircle2, Copy, ShieldAlert, TrendingUp, XCircle } from 'lucide-react'
import { useState } from 'react'
import styles from './UpbitKeyGuidePage.module.css'

const SERVER_IP = '34.233.225.79'

const ALLOW_PERMISSIONS = ['포켓관리', '자산조회', '주문조회', '주문하기', '출금조회', '입금조회', '입금하기']
const DENY_PERMISSION = '출금하기'

const STEPS = [
  {
    title: '1. Upbit 웹사이트에 로그인',
    body: 'upbit.com에 접속해 본인 계정으로 로그인합니다. 카카오페이 인증 등 2차 인증이 되어 있어야 합니다.',
  },
  {
    title: '2. 마이페이지 → Open API 관리로 이동',
    body: '로그인 후 우측 상단 마이페이지에서 "Open API 관리" 메뉴를 찾아 들어갑니다. 상단 탭 중 "Open API Key 관리"가 선택된 상태여야 합니다.',
  },
  {
    title: '3. 포켓 선택',
    body: '"포켓 선택"에서 "메인포켓"을 선택합니다.',
  },
  {
    title: '4. 권한 선택하기 (가장 중요합니다)',
    body: null,
  },
  {
    title: '5. IP 주소 등록',
    body: null,
  },
  {
    title: '6. 개인정보 동의 후 발급',
    body: '개인정보 수집 및 이용 동의를 체크하고 "Open API Key 발급받기"를 클릭합니다. OTP 또는 카카오페이 2차 인증을 거치면 Access Key와 Secret Key가 발급됩니다.',
  },
  {
    title: '7. Secret Key를 즉시 복사해 안전하게 보관',
    body: 'Secret Key는 발급 화면을 벗어나면 다시 확인할 수 없습니다. 반드시 그 자리에서 복사해 두세요. 잊어버렸다면 키를 삭제하고 새로 발급받아야 합니다.',
  },
  {
    title: '8. SignalTrade에 등록',
    body: '로그인 후 왼쪽 메뉴의 "계정 설정" → "Upbit API 연결"에서 Access Key와 Secret Key를 입력하고 저장하면, 자동으로 유효성을 검증한 뒤 암호화하여 저장합니다.',
  },
]

export default function UpbitKeyGuidePage() {
  const navigate = useNavigate()
  const [copied, setCopied] = useState(false)

  const copyIp = async () => {
    try {
      await navigator.clipboard.writeText(SERVER_IP)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // 클립보드 접근이 막힌 환경이면 사용자가 직접 선택해 복사하면 됩니다.
    }
  }

  return (
    <main className={styles.shell}>
      <div className={styles.inner}>
        <button className={styles.backLink} onClick={() => navigate(-1)}>
          <ArrowLeft size={16} /> 뒤로 가기
        </button>

        <div className={styles.brand}>
          <span className={styles.brandMark}><TrendingUp size={20} /></span>
          <span>SignalTrade</span>
        </div>

        <h1>Upbit API 키 발급 방법</h1>
        <p className={styles.lead}>
          SignalTrade가 여러분의 Upbit 계좌에서 자동으로 시세를 조회하고 주문을 실행하려면,
          Upbit에서 발급하는 API 키가 필요합니다. 아래 순서대로 진행해 주세요.
        </p>

        <div className={styles.stepList}>
          {STEPS.map((step) => (
            <section key={step.title} className={styles.step}>
              <h2>{step.title}</h2>
              {step.body && <p>{step.body}</p>}

              {step.title.startsWith('4.') && (
                <div className={styles.permissionBox}>
                  <p className={styles.permissionIntro}>
                    "권한 선택"에는 총 8개 항목이 있습니다. <strong>"출금하기" 한 개만 빼고 나머지 7개는 전부 체크</strong>해 주세요.
                  </p>
                  <div className={styles.permissionGrid}>
                    {ALLOW_PERMISSIONS.map((label) => (
                      <span key={label} className={styles.allow}>
                        <CheckCircle2 size={16} />
                        {label}
                      </span>
                    ))}
                    <span className={styles.deny}>
                      <XCircle size={16} />
                      {DENY_PERMISSION}
                    </span>
                  </div>
                  <div className={styles.warningCallout}>
                    <ShieldAlert size={18} />
                    <p>
                      SignalTrade는 자산 조회와 주문 기능만 사용하며, 출금 기능은 전혀 사용하지 않습니다.
                      출금하기 권한을 켜두면 혹시 키가 유출됐을 때 자산이 바로 인출될 수 있으니,
                      반드시 체크를 해제한 상태로 발급받아 주세요.
                    </p>
                  </div>
                </div>
              )}

              {step.title.startsWith('5.') && (
                <div className={styles.ipBox}>
                  <p>
                    "IP 주소 등록"란에 SignalTrade 서버의 IP 주소를 입력해야 합니다.
                    등록하지 않은 IP에서의 요청은 Upbit가 거부하므로 반드시 등록해야 합니다.
                  </p>
                  <div className={styles.ipRow}>
                    <code>{SERVER_IP}</code>
                    <button type="button" onClick={copyIp} className={styles.copyButton}>
                      <Copy size={14} /> {copied ? '복사됨' : '복사'}
                    </button>
                  </div>
                  <p className={styles.ipNote}>
                    여러 개의 IP를 등록해야 한다면 쉼표( , )로 구분해 입력할 수 있습니다.
                  </p>
                </div>
              )}
            </section>
          ))}
        </div>

        <div className={styles.footerNote}>
          <p>키 발급이 끝나셨다면 회원가입 후 로그인해 계정 설정에서 등록해 주세요.</p>
          <button className={styles.signupButton} onClick={() => navigate('/signup')}>
            회원가입 하러 가기
          </button>
        </div>
      </div>
    </main>
  )
}