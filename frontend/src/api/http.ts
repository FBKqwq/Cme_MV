import axios from 'axios'

const http = axios.create({
    baseURL: import.meta.env.VITE_API_BASE_URL || '',
    timeout: 15000,
    headers: {
        'Content-Type': 'application/json',
    },
})

http.interceptors.response.use(
    (response) => response,
    (error) => {
        console.error('接口请求失败：', error)
        return Promise.reject(error)
    },
)

export default http
