
// netlify/functions/site-config.js - COM SUA UPSTASH + SUPABASE
const { createClient } = require('@supabase/supabase-js');
const { Redis } = require('@upstash/redis');

exports.handler = async (event) => {
  const headers = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Content-Type': 'application/json'
  };
  
  if (event.httpMethod === 'OPTIONS') return {statusCode: 200, headers, body: ''};
  
  try {
    const companyId = event.queryStringParameters?.company_id || '00000000-0000-0000-0000-000000000001';
    
    // Tenta cache rápido na sua Upstash primeiro (sua URL do print)
    const redis = new Redis({
      url: "https://select-raptor-89663.upstash.io",
      token: "gQAAAAAAAV4_AAIgcDE1NTNiNDBlNWExNmI0Yzk4ODBkNjlkM2QzOTk3ZDcyZA"
    });
    
    const cached = await redis.get(`erp:afonsopena:site_settings:${companyId}`);
    if (cached) {
      return {statusCode: 200, headers, body: JSON.stringify(typeof cached === 'string' ? JSON.parse(cached) : cached)};
    }

    // Se não tem cache, busca Supabase
    const supabase = createClient(process.env.SUPABASE_URL, process.env.SUPABASE_ANON_KEY);
    const { data, error } = await supabase.from('site_settings').select('*').eq('company_id', companyId).single();
    
    if (error) throw error;
    
    // Salva no cache 60s na sua Upstash
    await redis.set(`erp:afonsopena:site_settings:${companyId}`, JSON.stringify(data), {ex: 60});
    
    return {statusCode: 200, headers, body: JSON.stringify(data)};
  } catch (err) {
    return {statusCode: 500, headers, body: JSON.stringify({error: err.message})};
  }
};
