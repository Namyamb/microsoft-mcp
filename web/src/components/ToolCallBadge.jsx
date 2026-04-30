const TOOL_ICONS = {
  outlook_get_emails: '📬',
  outlook_get_unread_emails: '📩',
  outlook_get_flagged_emails: '🚩',
  outlook_get_email_by_id: '📧',
  outlook_search_emails: '🔍',
  outlook_filter_emails_by_sender: '👤',
  outlook_filter_emails_by_date: '📅',
  outlook_send_email: '📤',
  outlook_create_draft: '📝',
  outlook_reply_email: '↩️',
  outlook_reply_all: '↩️',
  outlook_forward_email: '↪️',
  outlook_delete_email: '🗑️',
  outlook_archive_email: '📦',
  outlook_move_to_folder_name: '📁',
  outlook_mark_as_read: '✓',
  outlook_mark_as_unread: '●',
  outlook_flag_email: '🚩',
  outlook_unflag_email: '🏳️',
  outlook_list_folders: '📂',
  outlook_create_folder: '📁',
  outlook_list_categories: '🏷️',
  summarize_email: '✨',
  draft_reply: '✍️',
  resolve_email_id: '🔗',
}

const TOOL_LABELS = {
  outlook_get_emails: 'Fetching emails',
  outlook_get_unread_emails: 'Fetching unread emails',
  outlook_get_flagged_emails: 'Fetching flagged emails',
  outlook_get_email_by_id: 'Reading email',
  outlook_search_emails: 'Searching emails',
  outlook_filter_emails_by_sender: 'Filtering by sender',
  outlook_filter_emails_by_date: 'Filtering by date',
  outlook_send_email: 'Sending email',
  outlook_create_draft: 'Creating draft',
  outlook_reply_email: 'Sending reply',
  outlook_reply_all: 'Sending reply-all',
  outlook_forward_email: 'Forwarding email',
  outlook_delete_email: 'Deleting email',
  outlook_archive_email: 'Archiving email',
  outlook_move_to_folder_name: 'Moving email',
  outlook_mark_as_read: 'Marking as read',
  outlook_mark_as_unread: 'Marking as unread',
  outlook_flag_email: 'Flagging email',
  outlook_unflag_email: 'Removing flag',
  outlook_list_folders: 'Listing folders',
  outlook_create_folder: 'Creating folder',
  outlook_list_categories: 'Listing categories',
  summarize_email: 'Summarizing email',
  draft_reply: 'Drafting reply',
  resolve_email_id: 'Resolving email reference',
}

export default function ToolCallBadge({ name, status, result }) {
  const icon = TOOL_ICONS[name] || '⚙️'
  const label = TOOL_LABELS[name] || name.replace(/_/g, ' ')

  const isSuccess = status === 'done' && result?.success !== false
  const isError = status === 'done' && result?.success === false

  return (
    <div className={`tool-badge ${status === 'running' ? 'running' : isError ? 'error' : 'done'}`}>
      <span className="tool-icon">{icon}</span>
      <span className="tool-label">{label}</span>
      {status === 'running' && <span className="tool-spinner" />}
      {status === 'done' && isSuccess && <span className="tool-check">✓</span>}
      {status === 'done' && isError && <span className="tool-x">✗</span>}
    </div>
  )
}
