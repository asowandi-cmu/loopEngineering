/**
 * SourceBadge — per-row provenance chip for the trades table.
 *
 * Distinguishes manually entered trades (neutral "Manual") from broker-synced
 * trades (blue "Auto"), so a user scanning the journal can immediately tell which
 * rows the DXtrade pipeline produced. A `needs_review` trade additionally shows a
 * small amber "review" chip; when the trade was flagged as a likely duplicate of
 * an existing manual entry, that chip carries a `duplicate_of` tooltip so the user
 * can find the overlapping row rather than having a trade silently deleted.
 */
import type { Trade } from '@/journal/types'

interface SourceBadgeProps {
  source: Trade['source']
  reviewStatus: string
  duplicateOf?: number | null
}

export function SourceBadge({ source, reviewStatus, duplicateOf }: SourceBadgeProps) {
  const isAuto = source === 'dxtrade'
  const needsReview = reviewStatus === 'needs_review'
  const reviewTitle =
    duplicateOf != null
      ? `Possible duplicate of trade #${duplicateOf} — review before keeping both`
      : 'Needs review — unknown instrument tick spec'

  return (
    <span className="inline-flex items-center gap-1" data-testid="source-badge" data-source={source}>
      <span
        className={`inline-block rounded px-1.5 py-0.5 text-xs font-medium ${
          isAuto ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-600'
        }`}
      >
        {isAuto ? 'Auto' : 'Manual'}
      </span>
      {needsReview && (
        <span
          className="inline-block rounded px-1.5 py-0.5 text-xs font-medium bg-amber-100 text-amber-700 cursor-help"
          title={reviewTitle}
          data-testid="review-chip"
        >
          review
        </span>
      )}
    </span>
  )
}
