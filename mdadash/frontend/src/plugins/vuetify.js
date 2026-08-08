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
          primary: '#343131', // dark gray
          'on-primary': '#FFFFFF', // white
          secondary: '#808080', // gray
          'on-secondary': '#FFFFFF', // white
          background: '#E6E6E6', // light gray
          'on-background': '#343131', // dark gray
          surface: '#FFFFFF', // white
          'on-surface': '#343131', // dark gray
          info: '#FF9200', // orange
        },
      },
    },
  },
})
