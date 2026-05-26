export type MemberRole = 'owner' | 'admin' | 'editor' | 'viewer'

export type User = {
  id: string
  email: string
  display_name: string
  avatar_url?: string | null
}

export type ChannelListItem = {
  id: string
  name: string
  description?: string | null
  owner_id: string
  is_private: boolean
  invite_code?: string | null
  created_at: string
  role: MemberRole
}

export type ChannelDetail = ChannelListItem & {
  members: Array<{
    user_id: string
    email: string
    display_name: string
    avatar_url?: string | null
    role: MemberRole
    joined_at: string
  }>
  pages: PageSummary[]
}

export type PageSummary = {
  id: string
  title: string
  order_index: number
  is_branch: boolean
  branch_of?: string | null
  created_at: string
}

export type ElementType =
  | 'stroke'
  | 'rect'
  | 'ellipse'
  | 'text'
  | 'image'
  | 'math'
  | 'sticky'
  | 'arrow'
  | 'link'

export type ElementTransform = {
  x: number
  y: number
  scaleX: number
  scaleY: number
  rotation: number
}

export type ElementStyle = {
  stroke?: string
  fill?: string
  strokeWidth?: number
}

export type Element = {
  id: string
  page_id: string
  created_by?: string | null
  type: ElementType
  transform: ElementTransform
  style: ElementStyle
  content: Record<string, unknown>
  locked_by?: string | null
  is_deleted: boolean
  last_event?: string | null
  created_at: string
  updated_at: string
}

export type AuthSession = {
  accessToken: string
  refreshToken: string
  user: User
}
