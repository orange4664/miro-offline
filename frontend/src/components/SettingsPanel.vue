<template>
  <div class="settings-overlay" @click.self="$emit('close')">
    <div class="settings-modal">
      <div class="settings-header">
        <span class="settings-title">模型设置 / Model Settings</span>
        <button class="settings-close" @click="$emit('close')">×</button>
      </div>

      <div class="settings-body">
        <p class="settings-hint">留空表示保持当前不变。保存后对之后新建的模拟 / 报告 / 采访立即生效。</p>

        <!-- 主 LLM -->
        <div class="settings-section">
          <div class="section-title">主 LLM（生成 / 模拟 / 报告 / 采访）</div>
          <label>模型名 Model</label>
          <input v-model="llm.model" :placeholder="cur.llm.model || 'gpt-5.4-mini'" />
          <label>Base URL</label>
          <input v-model="llm.base_url" :placeholder="cur.llm.base_url || 'https://.../v1'" />
          <label>API Key</label>
          <input v-model="llm.api_key" type="password" :placeholder="cur.llm.api_key_masked || '未设置'" />
          <div class="row-test">
            <button class="btn-test" :disabled="testing.llm" @click="doTest('llm')">
              {{ testing.llm ? '测试中…' : '测试连接' }}
            </button>
            <span class="test-result" :class="testResult.llm.ok ? 'ok' : 'err'">{{ testResult.llm.msg }}</span>
          </div>
        </div>

        <!-- Embedding -->
        <div class="settings-section">
          <div class="section-title">Embedding（图谱向量化）</div>
          <label>Provider</label>
          <select v-model="emb.provider">
            <option value="">（不变）</option>
            <option value="openai">openai（兼容接口）</option>
            <option value="ollama">ollama</option>
            <option value="hash">hash（本地兜底）</option>
          </select>
          <label>模型名 Model</label>
          <input v-model="emb.model" :placeholder="cur.embedding.model || 'google/gemini-embedding-001'" />
          <label>Base URL</label>
          <input v-model="emb.base_url" :placeholder="cur.embedding.base_url || 'https://.../v1'" />
          <label>API Key</label>
          <input v-model="emb.api_key" type="password" :placeholder="cur.embedding.api_key_masked || '未设置'" />
          <label>向量维度 Dimension（改了需重建图谱）</label>
          <input v-model="emb.dimension" :placeholder="String(cur.embedding.dimension || 768)" />
          <div class="row-test">
            <button class="btn-test" :disabled="testing.embedding" @click="doTest('embedding')">
              {{ testing.embedding ? '测试中…' : '测试连接' }}
            </button>
            <span class="test-result" :class="testResult.embedding.ok ? 'ok' : 'err'">{{ testResult.embedding.msg }}</span>
          </div>
        </div>

        <div v-if="saveMsg" class="save-msg" :class="saveOk ? 'ok' : 'err'">{{ saveMsg }}</div>
      </div>

      <div class="settings-footer">
        <button class="btn-cancel" @click="$emit('close')">取消</button>
        <button class="btn-save" :disabled="saving" @click="doSave">{{ saving ? '保存中…' : '保存' }}</button>
      </div>
    </div>
  </div>
</template>
<script setup>
import { ref, reactive, onMounted } from 'vue'
import { getSettings, saveSettings, testConnection } from '../api/settings'

defineEmits(['close'])

const cur = reactive({
  llm: { model: '', base_url: '', api_key_masked: '' },
  embedding: { provider: 'openai', model: '', base_url: '', api_key_masked: '', dimension: 768 },
})
const llm = reactive({ model: '', base_url: '', api_key: '' })
const emb = reactive({ provider: '', model: '', base_url: '', api_key: '', dimension: '' })

const testing = reactive({ llm: false, embedding: false })
const testResult = reactive({ llm: { ok: false, msg: '' }, embedding: { ok: false, msg: '' } })
const saving = ref(false)
const saveMsg = ref('')
const saveOk = ref(false)

onMounted(async () => {
  try {
    const res = await getSettings()
    if (res.success && res.data) {
      Object.assign(cur.llm, res.data.llm)
      Object.assign(cur.embedding, res.data.embedding)
    }
  } catch (e) { /* ignore */ }
})

const doTest = async (target) => {
  testing[target] = true
  testResult[target] = { ok: false, msg: '' }
  try {
    const payload = target === 'llm'
      ? { target: 'llm', model: llm.model, base_url: llm.base_url, api_key: llm.api_key }
      : { target: 'embedding', provider: emb.provider, model: emb.model, base_url: emb.base_url, api_key: emb.api_key }
    const res = await testConnection(payload)
    testResult[target] = { ok: !!res.success, msg: res.success ? res.message : (res.error || '失败') }
  } catch (e) {
    testResult[target] = { ok: false, msg: e.message || '请求失败' }
  } finally {
    testing[target] = false
  }
}

const doSave = async () => {
  saving.value = true
  saveMsg.value = ''
  try {
    const res = await saveSettings({
      llm: { model: llm.model, base_url: llm.base_url, api_key: llm.api_key },
      embedding: {
        provider: emb.provider, model: emb.model, base_url: emb.base_url,
        api_key: emb.api_key, dimension: emb.dimension,
      },
    })
    saveOk.value = !!res.success
    saveMsg.value = res.success ? (res.message || '已保存') : (res.error || '保存失败')
    if (res.success) {
      const r = await getSettings()
      if (r.success) { Object.assign(cur.llm, r.data.llm); Object.assign(cur.embedding, r.data.embedding) }
      llm.api_key = ''; emb.api_key = ''
    }
  } catch (e) {
    saveOk.value = false
    saveMsg.value = e.message || '保存失败'
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.settings-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 9999; }
.settings-modal { background: #fff; width: 520px; max-width: 92vw; max-height: 88vh; border-radius: 10px; display: flex; flex-direction: column; overflow: hidden; box-shadow: 0 12px 40px rgba(0,0,0,0.25); }
.settings-header { display: flex; justify-content: space-between; align-items: center; padding: 16px 20px; border-bottom: 1px solid #eee; }
.settings-title { font-weight: 700; font-size: 16px; }
.settings-close { border: none; background: none; font-size: 24px; cursor: pointer; color: #888; line-height: 1; }
.settings-body { padding: 16px 20px; overflow-y: auto; }
.settings-hint { font-size: 12px; color: #888; margin: 0 0 14px; }
.settings-section { margin-bottom: 20px; }
.section-title { font-weight: 600; font-size: 14px; margin-bottom: 10px; color: #222; }
.settings-section label { display: block; font-size: 12px; color: #555; margin: 8px 0 4px; }
.settings-section input, .settings-section select { width: 100%; box-sizing: border-box; padding: 8px 10px; border: 1px solid #ddd; border-radius: 6px; font-size: 13px; }
.row-test { display: flex; align-items: center; gap: 10px; margin-top: 10px; }
.btn-test { padding: 6px 14px; border: 1px solid #4a6cf7; color: #4a6cf7; background: #fff; border-radius: 6px; cursor: pointer; font-size: 12px; }
.btn-test:disabled { opacity: .6; cursor: not-allowed; }
.test-result { font-size: 12px; }
.test-result.ok { color: #16a34a; }
.test-result.err { color: #dc2626; }
.save-msg { margin-top: 8px; font-size: 13px; }
.save-msg.ok { color: #16a34a; }
.save-msg.err { color: #dc2626; }
.settings-footer { display: flex; justify-content: flex-end; gap: 10px; padding: 14px 20px; border-top: 1px solid #eee; }
.btn-cancel { padding: 8px 18px; border: 1px solid #ddd; background: #fff; border-radius: 6px; cursor: pointer; }
.btn-save { padding: 8px 18px; border: none; background: #4a6cf7; color: #fff; border-radius: 6px; cursor: pointer; }
.btn-save:disabled { opacity: .6; cursor: not-allowed; }
</style>
