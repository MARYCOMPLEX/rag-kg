<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import BaseModal from '../base/BaseModal.vue'
import AppIcon from '../base/AppIcon.vue'
import { useWorkspaceNavigation } from '../../app/useWorkspaceNavigation'
import { useLibraryStore } from '../../stores/library'
import { useUiStore } from '../../stores/ui'

const ui = useUiStore()
const library = useLibraryStore()
const { libraryModalOpen } = storeToRefs(ui)
const { goToScreen } = useWorkspaceNavigation()

const name = ref('')
const slug = ref('')
const description = ref('')
const language = ref<'en' | 'zh' | 'multi'>('en')
const template = ref('survey')
const slugEdited = ref(false)
const creating = ref(false)
const languageOptions = ['en', 'zh', 'multi'] as const

const templates = [
  { id: 'empty', title: 'Empty', detail: 'Start with clean storage and defaults.' },
  { id: 'survey', title: 'Survey writer', detail: 'Review generation, citation rules, and KG-first retrieval.' },
  { id: 'code', title: 'Code research', detail: 'Snippets, repos, API docs, and architecture notes.' },
  { id: 'personal', title: 'Personal knowledge', detail: 'Notebook style retrieval with lighter indexing.' },
]

const slugStatus = computed(() => {
  if (!slug.value)
    return 'Required'
  if (slug.value.length < 3)
    return 'Too short'
  if (!/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(slug.value))
    return 'Use lowercase, digits, hyphens'
  return 'Checked on create'
})

const isSlugValid = computed(() => /^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(slug.value) && slug.value.length >= 3)
const slugStatusTone = computed(() => isSlugValid.value ? 'success' : 'danger')
const isCreateValid = computed(() => name.value.trim().length > 0 && isSlugValid.value)

watch(name, (next) => {
  if (slugEdited.value)
    return

  slug.value = next
    .toLowerCase()
    .replace(/[^a-z0-9\s-]/g, '')
    .trim()
    .replace(/\s+/g, '-')
    .replace(/-+/g, '-')
    .slice(0, 30)
})

function closeModal() {
  ui.libraryModalOpen = false
}

function setLanguage(option: typeof languageOptions[number]) {
  language.value = option
}

async function createLibrary() {
  if (!isCreateValid.value)
    return

  creating.value = true
  try {
    const result = await library.createLibrary({
      name: name.value.trim(),
      slug: slug.value.trim(),
      description: description.value.trim(),
      language: language.value,
      template: template.value,
    })
    closeModal()
    ui.pushToast('success', 'Library created', `Route ready at ${result.redirectTo}`, 'Open')
    await goToScreen('docs')
  }
  catch (error) {
    const detail = error instanceof Error ? error.message : 'Unable to create this library.'
    ui.pushToast('danger', 'Create failed', detail, 'Try again')
  }
  finally {
    creating.value = false
  }
}
</script>

<template>
  <BaseModal
    :show="libraryModalOpen"
    title="Create a new Library"
    subtitle="Set up a retrieval workspace with its own documents, graph, evaluation runs, and per-library overrides."
    size="md"
    close-label="Close create library modal"
    @update:show="ui.libraryModalOpen = $event"
  >
    <form id="create-library-form" class="create-library-form" @submit.prevent="createLibrary">
      <label class="form-field">
        <span>Display name</span>
        <input v-model="name" data-autofocus autocomplete="off" placeholder="Research library name">
      </label>

      <label class="form-field">
        <span>Slug</span>
        <div class="slug-input-wrap">
          <input
            v-model="slug"
            autocomplete="off"
            placeholder="research-library"
            aria-describedby="library-slug-help"
            @input="slugEdited = true"
          >
          <span class="slug-status" :class="slugStatusTone">
            <AppIcon :name="slugStatusTone === 'success' ? 'check' : 'warning'" :size="14" />
            {{ slugStatus }}
          </span>
        </div>
        <small id="library-slug-help">lowercase, digits, hyphens - permanent library URL segment</small>
      </label>

      <label class="form-field">
        <span>Description</span>
        <textarea v-model="description" maxlength="240" placeholder="Optional purpose or scope for this library." />
      </label>

      <fieldset class="language-control">
        <legend>Primary language</legend>
        <button
          v-for="option in languageOptions"
          :key="option"
          type="button"
          :class="{ active: language === option }"
          @click="setLanguage(option)"
        >
          {{ option }}
        </button>
      </fieldset>

      <fieldset class="template-grid">
        <legend>Template</legend>
        <label v-for="item in templates" :key="item.id" :class="{ active: template === item.id }">
          <input v-model="template" name="library-template" type="radio" :value="item.id">
          <strong>{{ item.title }}</strong>
          <small>{{ item.detail }}</small>
        </label>
      </fieldset>

      <div class="init-note">
        <AppIcon name="info" :size="16" />
        <span>Initializes vector storage and graph extraction defaults for this Library.</span>
      </div>
    </form>

    <template #footer>
      <span class="modal-key-hint">Enter submit · Esc close</span>
      <button class="modal-secondary-action" type="button" @click="closeModal">
        Cancel
      </button>
      <button class="modal-primary-action" type="submit" form="create-library-form" :disabled="creating || !isCreateValid">
        <AppIcon name="plus" :size="16" />
        {{ creating ? 'Creating...' : 'Create Library' }}
      </button>
    </template>
  </BaseModal>
</template>

<style scoped>
.create-library-form {
  display: grid;
  gap: 18px;
}

.form-field {
  display: grid;
  gap: 8px;
}

.form-field > span,
.language-control legend,
.template-grid legend {
  color: var(--color-on-surface-variant);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: .04em;
  line-height: 16px;
  text-transform: uppercase;
}

.form-field input,
.form-field textarea {
  width: 100%;
  border: 1px solid var(--color-border-field);
  border-radius: var(--radius-field);
  background: var(--color-surface-container-lowest);
  color: var(--color-on-surface);
  font-size: 14px;
  line-height: 20px;
  transition:
    border-color var(--motion-duration-fast) var(--motion-ease-standard),
    box-shadow var(--motion-duration-fast) var(--motion-ease-standard);
}

.form-field input {
  height: 44px;
  padding: 0 14px;
}

.form-field textarea {
  min-height: 72px;
  padding: 12px 14px;
  resize: none;
}

.form-field input:focus,
.form-field textarea:focus {
  border-color: var(--color-primary-container);
  box-shadow: var(--shadow-focus);
  outline: none;
}

.form-field small,
.template-grid small,
.modal-key-hint {
  color: var(--color-outline);
  font-size: 12px;
  line-height: 16px;
}

.slug-input-wrap {
  position: relative;
}

.slug-input-wrap input {
  padding-right: 148px;
}

.slug-status {
  position: absolute;
  top: 8px;
  right: 8px;
  display: inline-flex;
  align-items: center;
  height: 28px;
  gap: 4px;
  border-radius: var(--radius-pill);
  padding: 0 8px;
  font-size: 12px;
  font-weight: 600;
}

.slug-status.success {
  background: var(--color-success-50-exact);
  color: var(--color-success-700-exact);
}

.slug-status.danger {
  background: var(--color-danger-50-exact);
  color: var(--color-danger-700-exact);
}

.language-control,
.template-grid {
  display: grid;
  gap: 10px;
  margin: 0;
  border: 0;
  padding: 0;
}

.language-control {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.language-control legend,
.template-grid legend {
  grid-column: 1 / -1;
  padding: 0;
}

.language-control button {
  height: 36px;
  border: 1px solid var(--color-border-field);
  border-radius: var(--radius-control);
  background: var(--color-surface-container-lowest);
  color: var(--color-on-surface-variant);
  font-size: 13px;
  font-weight: 700;
  text-transform: uppercase;
}

.language-control button.active {
  border-color: var(--color-primary-container);
  background: var(--color-primary-fixed);
  color: var(--color-on-primary-fixed-variant);
}

.template-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.template-grid label {
  display: grid;
  min-height: 82px;
  gap: 4px;
  border: 1px solid var(--color-border-field);
  border-radius: var(--radius-card);
  background: var(--color-surface-container-lowest);
  padding: 12px;
  cursor: pointer;
}

.template-grid label.active {
  border-color: var(--color-primary-container);
  background: var(--color-primary-fixed);
}

.template-grid input {
  position: absolute;
  opacity: 0;
  pointer-events: none;
}

.template-grid strong {
  color: var(--color-on-surface);
  font-size: 14px;
  line-height: 20px;
}

.init-note {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  border: 1px solid var(--color-alpha-outline-variant-72);
  border-radius: var(--radius-card);
  background: var(--color-surface-container-low);
  padding: 12px;
  color: var(--color-on-surface-variant);
  font-size: 13px;
  line-height: 20px;
}

.modal-key-hint {
  margin-right: auto;
}

.modal-secondary-action,
.modal-primary-action {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: 40px;
  gap: 6px;
  border-radius: var(--radius-control);
  padding: 0 16px;
  font-size: 14px;
  font-weight: 700;
}

.modal-secondary-action {
  border: 1px solid var(--color-outline-variant);
  background: var(--color-surface-container-lowest);
  color: var(--color-on-surface);
}

.modal-primary-action {
  border: 1px solid var(--color-primary-container);
  background: var(--color-primary-container);
  color: var(--color-on-primary);
}

.modal-primary-action:disabled {
  border-color: transparent;
  background: var(--color-bg-disabled);
  color: var(--color-text-disabled);
  cursor: not-allowed;
}

@media (max-width: 640px) {
  .template-grid,
  .language-control {
    grid-template-columns: 1fr;
  }
}
</style>
