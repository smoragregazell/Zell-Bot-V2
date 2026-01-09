-- ============================================
-- TABLAS V2 PARA SUPABASE
-- ============================================
-- Tablas para logging de chat_v2 que coinciden exactamente
-- con la estructura de los CSVs existentes

-- ============================================
-- 1. conversation_logs_v2
-- ============================================
-- Estructura basada en: logs/chat_v2_interactions.csv
-- Columnas: timestamp, userName, conversation_id, user_message, response, 
--           response_id, rounds_used, had_previous_context, extra_info

CREATE TABLE IF NOT EXISTS conversation_logs_v2 (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "userName" TEXT,
    conversation_id TEXT NOT NULL,
    user_message TEXT,
    response TEXT,
    response_id TEXT,
    rounds_used INTEGER DEFAULT 0,
    had_previous_context TEXT,  -- "Yes" o "No" (igual que en CSV)
    extra_info TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Índices para mejor performance
CREATE INDEX IF NOT EXISTS idx_conversation_logs_v2_conversation_id 
    ON conversation_logs_v2(conversation_id);
CREATE INDEX IF NOT EXISTS idx_conversation_logs_v2_timestamp 
    ON conversation_logs_v2(timestamp);
CREATE INDEX IF NOT EXISTS idx_conversation_logs_v2_response_id 
    ON conversation_logs_v2(response_id);

-- ============================================
-- 2. token_usage_v2
-- ============================================
-- Estructura basada en: logs/chat_v2_token_usage.csv
-- Columnas: timestamp, conversation_id, response_id, round, model,
--           input_tokens_total, cached_tokens, input_tokens_real, output_tokens,
--           total_tokens, cost_input_usd, cost_cached_usd, cost_output_usd,
--           cost_total_usd, web_search_used, tools_called

CREATE TABLE IF NOT EXISTS token_usage_v2 (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    conversation_id TEXT NOT NULL,
    response_id TEXT NOT NULL,
    round INTEGER NOT NULL,
    model TEXT,
    input_tokens_total INTEGER DEFAULT 0,
    cached_tokens INTEGER DEFAULT 0,
    input_tokens_real INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0,
    cost_input_usd NUMERIC(10, 6) DEFAULT 0.0,
    cost_cached_usd NUMERIC(10, 6) DEFAULT 0.0,
    cost_output_usd NUMERIC(10, 6) DEFAULT 0.0,
    cost_total_usd NUMERIC(10, 6) DEFAULT 0.0,
    web_search_used TEXT,  -- "Yes" o "No" (igual que en CSV)
    tools_called TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Índices para mejor performance
CREATE INDEX IF NOT EXISTS idx_token_usage_v2_conversation_id 
    ON token_usage_v2(conversation_id);
CREATE INDEX IF NOT EXISTS idx_token_usage_v2_response_id 
    ON token_usage_v2(response_id);
CREATE INDEX IF NOT EXISTS idx_token_usage_v2_timestamp 
    ON token_usage_v2(timestamp);
CREATE INDEX IF NOT EXISTS idx_token_usage_v2_round 
    ON token_usage_v2(conversation_id, round);

-- ============================================
-- 3. ai_calls_v2
-- ============================================
-- Estructura similar a ai_calls pero adaptada para V2
-- Basada en la estructura de log_token_usage_postgres pero más completa

CREATE TABLE IF NOT EXISTS ai_calls_v2 (
    id SERIAL PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    interaction_id TEXT,  -- response_id de V2
    call_type TEXT,  -- "V2 Response"
    model TEXT,
    provider TEXT DEFAULT 'openai',
    temperature NUMERIC(5, 2),
    confidence_score NUMERIC(5, 2),
    messages JSONB,  -- JSON con información del round
    response JSONB,  -- JSON con response_id, round, model, version
    token_usage JSONB,  -- JSON completo con todos los datos de tokens y costos
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Índices para mejor performance
CREATE INDEX IF NOT EXISTS idx_ai_calls_v2_conversation_id 
    ON ai_calls_v2(conversation_id);
CREATE INDEX IF NOT EXISTS idx_ai_calls_v2_interaction_id 
    ON ai_calls_v2(interaction_id);
CREATE INDEX IF NOT EXISTS idx_ai_calls_v2_timestamp 
    ON ai_calls_v2(timestamp);
CREATE INDEX IF NOT EXISTS idx_ai_calls_v2_model 
    ON ai_calls_v2(model);

-- Índices GIN para búsquedas en JSONB
CREATE INDEX IF NOT EXISTS idx_ai_calls_v2_token_usage_gin 
    ON ai_calls_v2 USING GIN(token_usage);

-- ============================================
-- COMENTARIOS PARA DOCUMENTACIÓN
-- ============================================

COMMENT ON TABLE conversation_logs_v2 IS 
'Log de interacciones completas de chat_v2. Cada fila representa una interacción usuario-sistema completa.';

COMMENT ON TABLE token_usage_v2 IS 
'Log detallado de uso de tokens por round de chat_v2. Incluye costos y herramientas usadas.';

COMMENT ON TABLE ai_calls_v2 IS 
'Log de llamadas a Responses API en V2. Incluye información completa de tokens, costos y contexto en formato JSONB.';

COMMENT ON COLUMN conversation_logs_v2.had_previous_context IS 
'Valor "Yes" o "No" indicando si había contexto previo de conversación.';

COMMENT ON COLUMN token_usage_v2.web_search_used IS 
'Valor "Yes" o "No" indicando si se usó web_search en este round.';

COMMENT ON COLUMN token_usage_v2.tools_called IS 
'Lista de herramientas llamadas separadas por comas (ej: "search_knowledge, get_item").';

