import { io } from 'socket.io-client'

export const socket = io('', {
  autoConnect: true,
})

socket.on('connect', () => {})

socket.on('disconnect', () => {})
