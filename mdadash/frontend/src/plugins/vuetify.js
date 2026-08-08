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
    themes: {
      light: {
        colors: {
          primary: '#FF9200', // orange
          'on-primary': '#000000', // black
          secondary: '#343131', // dark gray
          'on-secondary': '#FFFFFF', // white
          background: '#E6E6E6', // light gray
          'on-background': '#343131', // dark gray
          surface: '#FFFFFF', // white
          'on-surface': '#343131', // dark gray
          info: '#343131', // dark gray
        },
      },
    },
  },
})
