export type ConnectionState = 'connecting' | 'online' | 'offline'

export interface User {
  id: string
  name: string
  color: string
}

export interface CommentRecord {
  id: string
  author: User
  body: string
  createdAt: number
  resolved: boolean
  anchor: string
  head: string
}

export interface VersionRecord {
  id: string
  label: string
  author: Pick<User, 'id' | 'name'>
  createdAt: string
  preview: string
}

export type SidePanel = 'comments' | 'history' | null
