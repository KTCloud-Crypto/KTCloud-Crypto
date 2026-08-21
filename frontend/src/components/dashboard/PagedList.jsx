import { useState } from 'react'
import { ChevronDown, ChevronLeft, ChevronRight } from 'lucide-react'
import styles from './PagedList.module.css'

const PAGE_SIZE = 10
const PREVIEW_SIZE = 2

export default function PagedList({ items, renderItem, emptyLabel = '내역이 없습니다.' }) {
  const [expanded, setExpanded] = useState(false)
  const [page, setPage] = useState(0)

  if (items.length === 0) {
    return <div className={styles.empty}>{emptyLabel}</div>
  }

  const totalPages = Math.max(1, Math.ceil(items.length / PAGE_SIZE))
  const visibleItems = expanded
    ? items.slice(page * PAGE_SIZE, page * PAGE_SIZE + PAGE_SIZE)
    : items.slice(0, PREVIEW_SIZE)

  const toggleExpanded = () => {
    setExpanded((current) => !current)
    setPage(0)
  }

  return (
    <div className={styles.wrap}>
      <div className={styles.list}>
        {visibleItems.map(renderItem)}
      </div>

      {items.length > PREVIEW_SIZE && (
        <button type="button" className={styles.toggleButton} onClick={toggleExpanded}>
          {expanded ? '접기' : '더 보기'}
          <ChevronDown className={expanded ? styles.chevronOpen : ''} size={16} />
        </button>
      )}

      {expanded && totalPages > 1 && (
        <div className={styles.pager}>
          <button
            type="button"
            onClick={() => setPage((current) => Math.max(0, current - 1))}
            disabled={page === 0}
            aria-label="이전 페이지"
          >
            <ChevronLeft size={16} />
            <span>이전</span>
          </button>
          <strong>{page + 1} / {totalPages}</strong>
          <button
            type="button"
            onClick={() => setPage((current) => Math.min(totalPages - 1, current + 1))}
            disabled={page === totalPages - 1}
            aria-label="다음 페이지"
          >
            <span>다음</span>
            <ChevronRight size={16} />
          </button>
        </div>
      )}
    </div>
  )
}
