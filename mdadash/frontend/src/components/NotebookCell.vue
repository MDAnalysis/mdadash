<template>
  <v-container class="pa-0">
    <div :id="id" class="mb-0">
      <v-card class="border rounded-lg">
        <v-card-actions
          @dblclick="show = !show"
          style="user-select: none"
          class="bg-grey-lighten-5 py-0 px-3 border-b"
        >
          <!-- Drag cell -->
          <v-icon
            v-if="showDrag"
            :icon="mdiDrag"
            class="drag-handle cursor-move text-grey-lighten-1"
            size="small"
            v-tooltip:bottom="'Drag cell'"
          ></v-icon>
          <!-- Show / Hide cell -->
          <v-btn
            :icon="show ? mdiUnfoldLessHorizontal : mdiUnfoldMoreHorizontal"
            variant="text"
            size="small"
            color="grey-darken-1"
            @click="show = !show"
            v-tooltip:bottom="show ? 'Hide cell' : 'Show cell'"
          ></v-btn>
          <span class="text-caption font-weight-bold text-grey-darken-1">{{ label }}</span>
          <v-spacer></v-spacer>
          <!-- Move up -->
          <v-btn
            v-if="showMove"
            :icon="mdiChevronUp"
            color="grey-darken-1"
            variant="text"
            size="small"
            @click="$emit('move-up')"
            v-tooltip:bottom="'Move up'"
          ></v-btn>
          <!-- Move down -->
          <v-btn
            v-if="showMove"
            :icon="mdiChevronDown"
            color="grey-darken-1"
            variant="text"
            size="small"
            @click="$emit('move-down')"
            v-tooltip:bottom="'Move down'"
          ></v-btn>
          <!-- Run cell -->
          <v-btn
            :icon="mdiPlayOutline"
            color="success"
            variant="text"
            size="small"
            @click="runCell()"
            :disabled="isRunning"
            v-tooltip:bottom="'Run cell'"
          ></v-btn>
          <!-- Delete cell -->
          <v-btn
            v-if="showDelete"
            :icon="mdiDeleteOutline"
            color="error"
            variant="text"
            size="small"
            @click="deleteCell()"
            :disabled="isRunning"
            v-tooltip:bottom="'Delete cell'"
          ></v-btn>
        </v-card-actions>
        <!-- Cell contents -->
        <v-expand-transition>
          <div v-show="show">
            <!-- Code Editor -->
            <v-card-text class="pa-0">
              <codemirror
                v-model="code"
                placeholder="# Python code here... "
                :extensions="getExtensions()"
                :style="{ minHeight: '100px' }"
                @blur="emitChange"
              />
              <!-- Output -->
              <v-card-text v-if="outputs?.length" class="bg-white border-t pa-4 font-mono">
                <div v-for="(out, idx) in outputs" :key="idx" class="mb-2">
                  <pre v-if="out.type === 'text'" class="text-body-2 text-pre-wrap">{{
                    out.content
                  }}</pre>
                  <v-alert
                    v-if="out.type === 'error'"
                    type="error"
                    variant="tonal"
                    density="compact"
                    class="text-caption"
                  >
                    {{ out.content }}
                  </v-alert>
                  <v-img
                    v-if="out.type === 'image'"
                    :src="'data:image/jpeg;base64,' + out.content"
                    class="rounded mt-2"
                    max-height="400"
                    contain
                  ></v-img>
                </div>
              </v-card-text>
            </v-card-text>
          </div>
        </v-expand-transition>
      </v-card>
      <!-- Add Cell button -->
      <div v-if="showAddCell" class="add-cell-container my-0">
        <v-btn
          :prepend-icon="mdiPlus"
          variant="flat"
          color="grey-lighten-4"
          class="text-grey-darken-1 full-width-btn"
          block
          rounded="sm"
          @click="$emit('add-cell')"
        >
          Add Cell
        </v-btn>
      </div>
      <!-- Hint -->
      <div v-if="hint" class="hint">
        {{ hint }}
      </div>
    </div>
  </v-container>
</template>

<script setup>
import { socket } from '@/socket'
import { inject, ref } from 'vue'
import {
  mdiDrag,
  mdiDeleteOutline,
  mdiPlayOutline,
  mdiPlus,
  mdiUnfoldLessHorizontal,
  mdiUnfoldMoreHorizontal,
  mdiChevronUp,
  mdiChevronDown,
} from '@mdi/js'
import { Codemirror } from 'vue-codemirror'
import { python } from '@codemirror/lang-python'
import { keymap, tooltips } from '@codemirror/view'
import { Prec } from '@codemirror/state'
import { autocompletion } from '@codemirror/autocomplete'
import { indentUnit } from '@codemirror/language'
import { AnsiUp } from 'ansi_up'

const settings = inject('settings')
const ansiUp = new AnsiUp()
ansiUp.escape_for_html = true
const code = defineModel()
const show = ref(true)
const outputs = ref([])
const isRunning = ref(false)
let originalCode = code.value

const props = defineProps({
  id: String,
  label: String,
  showDrag: Boolean,
  showMove: Boolean,
  showDelete: Boolean,
  showAddCell: Boolean,
  hint: String,
})

const emit = defineEmits([
  'change',
  'add-cell',
  'delete-cell',
  'move-up',
  'move-down',
  'focus-next',
])

// v8 ignore next
const autoComplete = () => {
  return async (context) => {
    const { state, pos } = context
    const word = context.matchBefore(/\.?\w*/)
    if (!word || (word.from == word.to && !context.explicit)) return null
    return new Promise((resolve) => {
      socket.emit('cell_code_complete', { code: state.doc.toString(), cursor_pos: pos }, (data) => {
        if (!data || data.status !== 'ok') return resolve(null)
        resolve({
          from: data.cursor_start,
          to: data.cursor_end,
          options: data.matches.map((m) => ({
            label: m,
            type: 'variable',
            info: async () => {
              const { state, pos } = context
              const line = state.doc.lineAt(pos)
              const word = context.matchBefore(/\w*/)
              const linePrefix = line.text.slice(0, word.from - line.from)
              const lineSuffix = line.text.slice(pos - line.from)
              const reconstructedLine = linePrefix + m + lineSuffix
              const newCursorPos = word.from - line.from + m.length
              return new Promise((resolve) => {
                socket.emit(
                  'cell_code_inspect',
                  {
                    code: reconstructedLine,
                    cursor_pos: newCursorPos,
                  },
                  (reply) => {
                    if (!reply || !reply.found) return resolve(null)
                    const container = document.createElement('div')
                    container.innerHTML = `<pre>${ansiUp.ansi_to_html(reply.data['text/plain'])}</pre>`
                    resolve({ dom: container })
                  },
                )
              })
            },
          })),
        })
      })
    })
  }
}

const getExtensions = () => {
  return [
    python(),
    indentUnit.of('    '),
    autocompletion({ override: [autoComplete()] }),
    tooltips({ parent: document.body }),
    Prec.highest(
      keymap.of([
        {
          key: 'Ctrl-Enter',
          run: () => {
            runCell()
            return true
          },
        },
        {
          key: 'Cmd-Enter',
          run: () => {
            runCell()
            return true
          },
        },
        {
          key: 'Shift-Enter',
          run: () => {
            runCell()
            emit('focus-next')
            return true
          },
        },
      ]),
    ),
  ]
}

// v8 ignore next
const emitChange = () => {
  if (originalCode !== code.value) {
    emit('change')
    originalCode = code.value
  }
}

const runCell = async () => {
  if (isRunning.value) return
  emitChange()
  outputs.value = []
  isRunning.value = true
  try {
    const response = await socket
      .timeout(settings.value.dashboard_config.ui_request_timeout * 1000)
      .emitWithAck('cell_run', JSON.stringify({ cell_id: props.id, code: code.value }))
    outputs.value = response
  } finally {
    isRunning.value = false
  }
}

const deleteCell = () => {
  code.value = ''
  outputs.value = []
  emit('delete-cell')
}
</script>

<style scoped>
/* Cell card styles */
.v-card {
  transition: box-shadow 0.2s;
}
.v-card:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.25) !important;
}
/* Codemirror styles */
.cm-editor {
  border: none !important;
  padding: 8px 0;
}
.cm-focused {
  outline: none !important;
}
/* Add cell styles */
.add-cell-container {
  opacity: 0.4;
  transition: opacity 0.2s;
}
.add-cell-container:hover {
  opacity: 1;
}
.full-width-btn {
  border: 1px dashed #e0e0e0 !important;
  text-transform: none !important;
  letter-spacing: normal;
  height: 32px !important;
}
.full-width-btn:hover {
  background-color: #f5f5f5 !important;
  border-style: solid !important;
  border-color: #bdbdbd !important;
}
/* Hint */
.hint {
  font-size: 12px;
  color: #757575;
  margin-top: 8px;
  padding-left: 16px;
}
</style>

<style>
/* Codemirror - complete and inspect response styles */
.cm-tooltip-autocomplete {
  z-index: 9999 !important;
}
.cm-tooltip.cm-completionInfo {
  min-width: 300px;
  width: auto;
  max-width: 600px;
  max-height: 400px;
  overflow-y: auto;
  font-size: 12px;
  line-height: 1.5;
}
.cm-tooltip.cm-completionInfo pre {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
}
/* a height of 100px for codemirror code complete stuff gets added
  by default at bottom of layout. Suppress this */
[class^='ͼ'] {
  min-height: 0 !important;
}
</style>
