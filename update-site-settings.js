
// netlify/functions/update-site-settings.js - SALVA + LIMPA CACHE UPSTASH
const { createClient } = require('@supabase/supabase-js');
const { Redis } = require('@upstash/redis');

exports.handler = async (event) => {
  const headers = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Content-Type': 'application/json'
  };
  
  if (event.httpMethod === 'OPTIONS') return {statusCode: 200, headers, body: ''};
  
  try {
    const body = JSON.parse(event.body);
    const supabase = createClient(process.env.SUPABASE_URL, process.env.SUPABASE_SERVICE_KEY);
    
    const { data, error } = await supabase.from('site_settings').upsert({
      company_id: body.company_id || '00000000-0000-0000-0000-000000000001',
      company_name: body.company_name,
      primary_color: body.primary_color,
      secondary_color: body.secondary_color,
      logo_url: body.logo_url,
      banners: body.banners,
      contacts: body.contacts,
      updated_at: new Date().toISOString()
    }, {onConflict: 'company_id'}).select().single();
    
    if (error) throw error;
    
    // Limpa cache na sua Upstash pra atualizar site na hora
    const redis = new Redis({url: "https://select-raptor-89663.upstash.io", token: "gQAAAAAAAV4_AAIgcDE1NTNiNDBlNWExNmI0Yzk4ODBkNjlkM2QzOTk3ZDcyZA"});
    await redis.del(`erp:afonsopena:site_settings:${body.company_id || '00000000-0000-0000-0000-000000000001'}`);
    
    return {statusCode: 200, headers, body: JSON.stringify({success: true, data})};
  } catch (err) {
    return {statusCode: 500, headers, body: JSON.stringify({error: err.message})};
  }
};
