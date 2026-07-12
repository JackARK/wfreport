import axios from 'axios'
const base = 'http://localhost:8000'
export const upload = (file) => { const fd = new FormData(); fd.append('file', file); return axios.post(base+'/api/upload', fd) }
export const preview = (wid) => axios.post(base+'/api/preview/'+wid)
export const aiSection = (section, body) => axios.post(base+'/api/ai/'+section, body)
export const getPrompts = () => axios.get(base+'/api/config/prompts')
export const putPrompts = (body) => axios.put(base+'/api/config/prompts', body)
export const generate = (wid, body) => axios.post(base+'/api/generate/'+wid, body)
export const dl = (wid, name) => base+'/api/download/'+wid+'/'+name
