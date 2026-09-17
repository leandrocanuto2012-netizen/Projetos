 const { createClient } = require('@supabase/supabase-js');
const { Redis } = require('@upstash/redis');
exports.handler = async (event) => {
  const headers = {'Access-Control-Allow-Origin':'*','Access-Control-Allow-Headers':'Content-Type','Content-Type':'application/json'};
  if (event.httpMethod === 'OPTIONS') return {statusCode:200,headers,body:''};
  try {
    const companyId = event.queryStringParameters?.company_id || '00000000-0000-0000-0000-000000000001';
    const redis = new Redis({
      url: process.env.UPSTASH_REDIS_REST_URL || process.env.REDIS_URL,
      token: process.env.UPSTASH_REDIS_REST_TOKEN || process.env.REDIS_TOKEN,
    });
    const PREFIX = process.env.REDIS_PREFIX || 'erp:afonsopena:';
    const cached = await redis.get(`${PREFIX}site_config:${companyId}`);
    if (cached) return {statusCode:200,headers,body:JSON.stringify(cached)};
    const supabase = createClient(process.env.SUPABASE_URL, process.env.SUPABASE_KEY);
    const {data,error} = await supabase.from('site_settings').select('*').eq('company_id',companyId).single();
    if (error) throw error;
    await redis.set(`${PREFIX}site_config:${companyId}`,data,{ex:60});
    return {statusCode:200,headers,body:JSON.stringify(data)};
  } catch(e){return {statusCode:500,headers,body:JSON.stringify({error:e.message})}}
};