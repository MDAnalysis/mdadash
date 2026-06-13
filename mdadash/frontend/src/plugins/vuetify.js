import { aliases, mdi } from 'vuetify/iconsets/mdi-svg'
import 'vuetify/styles'

import { createVuetify } from 'vuetify'

export default createVuetify({
  icons: {
    defaultSet: 'mdi',
    aliases,
    sets: {
      mdi,
    },
  },
  theme: {
    defaultTheme: 'light',
  },
})
