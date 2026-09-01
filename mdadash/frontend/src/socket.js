import { io } from 'socket.io-client'

export const socket = io('', {
  transports: ['websocket', 'polling'],
  timeout: 5000,
  autoConnect: true,
})

socket.on('connect_error', () => {
  socket.io.opts.transports = ['polling', 'websocket']
})

socket.io.on('reconnect_attempt', () => {
  socket.io.opts.transports = ['websocket', 'polling']
})

socket.on('connect', () => {
  let initDataRequested = false
  const requestInitData = () => {
    if (initDataRequested) {
      return
    }
    socket.emit('init_data')
    initDataRequested = true
  }
  if (socket.io.engine.transport.name === 'websocket') {
    requestInitData()
  } else {
    const handleUpgrade = (transport) => {
      if (transport.name === 'websocket') {
        clearTimeout(upgradeTimeout)
        requestInitData()
      }
    }
    socket.io.engine.once('upgrade', handleUpgrade)
    const upgradeTimeout = setTimeout(() => {
      socket.io.engine.off('upgrade', handleUpgrade)
      requestInitData()
    }, 2000)
  }
})
