import yaml from 'js-yaml'

/** Parse a YAML string into a plain object. */
export function parseYaml(text: string): Record<string, any> {
  const result = yaml.load(text)
  if (typeof result !== 'object' || result === null || Array.isArray(result)) {
    throw new Error('Expected YAML to parse to an object')
  }
  return result as Record<string, any>
}

/** Serialize a plain object to a YAML string. */
export function dumpYaml(data: Record<string, any>): string {
  return yaml.dump(data, { lineWidth: 120, noRefs: true, sortKeys: false })
}

/** Trigger a browser download of `data` as a YAML file. */
export function downloadYaml(data: Record<string, any>, filename: string): void {
  const text = dumpYaml(data)
  const blob = new Blob([text], { type: 'text/yaml;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename.endsWith('.yaml') ? filename : `${filename}.yaml`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

/** Copy `data` as YAML text to the clipboard. */
export async function copyYamlToClipboard(data: Record<string, any>): Promise<void> {
  const text = dumpYaml(data)
  await navigator.clipboard.writeText(text)
}

/** Open a file picker dialog and return the parsed YAML content. */
export function importYamlFile(): Promise<Record<string, any>> {
  return new Promise((resolve, reject) => {
    const input = document.createElement('input')
    input.type = 'file'
    input.accept = '.yaml,.yml'

    input.addEventListener('change', () => {
      const file = input.files?.[0]
      if (!file) {
        reject(new Error('No file selected'))
        return
      }
      const reader = new FileReader()
      reader.onload = () => {
        try {
          const result = parseYaml(reader.result as string)
          resolve(result)
        } catch (err) {
          reject(err)
        }
      }
      reader.onerror = () => reject(new Error('Failed to read file'))
      reader.readAsText(file)
    })

    // Handle cancel — the change event won't fire
    input.addEventListener('cancel', () => {
      reject(new Error('File selection cancelled'))
    })

    input.click()
  })
}
