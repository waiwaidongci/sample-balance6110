import{request,download}from './client';import type{Run,BootstrapAnalysis}from '../types/domain';
export const getRuns=()=>request<Run[]>('/runs');export const getRun=(id:number)=>request<Run>(`/runs/${id}`);
export const createRun=(data:unknown)=>request<Run>('/runs',{method:'POST',body:JSON.stringify(data)});
export const exportRun=(id:number)=>download(`/runs/${id}/export`,`yy-weights-${id}.csv`);
export const getBootstraps=(runId:number)=>request<BootstrapAnalysis[]>(`/bootstrap/runs/${runId}`);
export const createBootstrap=(runId:number,data:{replicates:number;seed:number})=>request<BootstrapAnalysis>(`/bootstrap/runs/${runId}`,{method:'POST',body:JSON.stringify(data)});
