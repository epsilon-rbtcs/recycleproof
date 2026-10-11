export const API = import.meta.env.VITE_API_BASE_URL || '';
const DEMO_TOKEN_KEY = 'rp_demo_token';

export function token(){return localStorage.getItem('rp_token')||''}
export function demoToken(){return localStorage.getItem(DEMO_TOKEN_KEY)||''}
export function storeDemoToken(value:string){localStorage.setItem(DEMO_TOKEN_KEY,value)}
export function clearDemoToken(){localStorage.removeItem(DEMO_TOKEN_KEY)}

async function send(path:string, options:RequestInit={}, accessToken=''){
  const headers=new Headers(options.headers||{});
  if(accessToken)headers.set('Authorization',`Bearer ${accessToken}`);
  if(options.body && !(options.body instanceof FormData) && !headers.has('Content-Type'))headers.set('Content-Type','application/json');
  const res=await fetch(`${API}/api${path}`,{...options,headers});
  const data=await res.json().catch(()=>({detail:res.statusText}));
  if(!res.ok){const error=new Error(typeof data.detail==='string'?data.detail:`Request failed (${res.status})`) as Error&{status:number};error.status=res.status;throw error;}
  return data;
}

// Existing real-user API calls continue to use only rp_token.
export function request(path:string, options:RequestInit={}){return send(path,options,token())}
// Session creation is intentionally anonymous; don't forward a logged-in user's bearer token.
export function publicRequest(path:string, options:RequestInit={}){return send(path,options,'')}
// Demo data APIs always use their distinct rp_demo_token credential.
export function demoRequest(path:string, options:RequestInit={}){
  const value=demoToken();
  if(!value){const error=new Error('Demo session missing. Start a fresh demo session.') as Error&{status:number};error.status=401;return Promise.reject(error)}
  return send(path,options,value);
}
