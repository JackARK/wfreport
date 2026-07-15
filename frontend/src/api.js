import axios from 'axios'

const base = 'http://localhost:8000'

// ---- upload / legacy ----
export const upload        = (file) => { const fd = new FormData(); fd.append('file', file); return axios.post(base+'/api/upload', fd) }
export const preview       = (wid) => axios.post(base+'/api/preview/'+wid)
export const aiSection     = (section, body) => axios.post(base+'/api/ai/'+section, body)
export const getPrompts    = () => axios.get(base+'/api/config/prompts')
export const putPrompts    = (body) => axios.put(base+'/api/config/prompts', body)
export const generate      = (wid, body) => axios.post(base+'/api/generate/'+wid, body)
export const dl            = (wid, name) => base+'/api/download/'+wid+'/'+name

// ---- workflow workspace ----
export const getWorkspace      = (wid) => axios.get(base+'/api/workspace/'+wid).then(r => r.data)
export const putWorkspace      = (wid, body) => axios.put(base+'/api/workspace/'+wid, body).then(r => r.data)
export const buildFull         = (wid, body) => axios.post(base+'/api/workspace/'+wid+'/build', body || {}).then(r => r.data)
export const downloadBundle    = (wid) => base+'/api/bundle/'+wid+'.zip'

// ---- history ----
export const getHistory        = () => axios.get(base+'/api/history').then(r => r.data)
export const listHistory       = () => axios.get(base+'/api/history/all').then(r => r.data)
export const reloadWorkspace   = (wid) => axios.post(base+'/api/workspace/'+wid+'/reload').then(r => r.data)
export const workspaceExportUrl = (wid) => base+'/api/workspace/'+wid+'/export.json'
