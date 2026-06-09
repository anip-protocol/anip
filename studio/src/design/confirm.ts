import { reactive } from 'vue'

export interface ConfirmationRequest {
  title: string
  message: string
  confirmLabel?: string
  cancelLabel?: string
  tone?: 'danger' | 'neutral'
}

interface ConfirmationState extends ConfirmationRequest {
  open: boolean
}

let pendingResolver: ((value: boolean) => void) | null = null

export const confirmationStore = reactive<ConfirmationState>({
  open: false,
  title: '',
  message: '',
  confirmLabel: 'Confirm',
  cancelLabel: 'Cancel',
  tone: 'danger',
})

export function requestConfirmation(request: ConfirmationRequest): Promise<boolean> {
  if (pendingResolver) {
    pendingResolver(false)
    pendingResolver = null
  }

  confirmationStore.open = true
  confirmationStore.title = request.title
  confirmationStore.message = request.message
  confirmationStore.confirmLabel = request.confirmLabel ?? 'Confirm'
  confirmationStore.cancelLabel = request.cancelLabel ?? 'Cancel'
  confirmationStore.tone = request.tone ?? 'danger'

  return new Promise<boolean>((resolve) => {
    pendingResolver = resolve
  })
}

export function resolveConfirmation(result: boolean) {
  if (pendingResolver) {
    pendingResolver(result)
    pendingResolver = null
  }
  confirmationStore.open = false
}
