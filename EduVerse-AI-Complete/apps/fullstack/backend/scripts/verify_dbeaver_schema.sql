-- =====================================================================
-- EduVerse AI — PostgreSQL Database Inspection & Verification Script
-- Target Database: eduverse_db
-- Target User:     eduverse_app
-- Host:            127.0.0.1:5432
-- =====================================================================

-- 1. Verify Current Connection & Schema
SELECT 
    current_database() AS database_name,
    current_user AS connected_user,
    version() AS postgresql_version;

-- 2. Total Table Count
SELECT count(*) AS total_tables
FROM information_schema.tables 
WHERE table_schema = 'public';

-- 3. Detailed Row Counts Across All EduVerse AI Tables
SELECT 
    table_name,
    (xpath('/row/cnt/text()', xml_count))[1]::text::int AS row_count
FROM (
    SELECT 
        table_name, 
        query_to_xml(format('SELECT count(*) AS cnt FROM %I.%I', table_schema, table_name), false, true, '') AS xml_count
    FROM information_schema.tables
    WHERE table_schema = 'public'
) t
ORDER BY row_count DESC, table_name ASC;

-- 4. Verify Academic Domain Tables & Multi-tenant Keys
SELECT table_name, column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name IN (
    'courses', 'course_units', 'syllabus_topics', 'course_outcomes',
    'previous_papers', 'exam_questions', 'exam_sessions', 'assessment_questions',
    'answer_attempts', 'grading_feedback', 'student_topic_mastery', 'revision_plans'
) AND column_name IN ('id', 'user_id', 'course_id', 'score_awarded', 'mastery_score')
ORDER BY table_name, column_name;

-- 5. Verify Full-Text Search (tsvector & GIN Index)
SELECT 
    schemaname, tablename, indexname, indexdef
FROM pg_indexes
WHERE tablename = 'search_docs' AND indexname LIKE '%tsv%';

-- Test Full-Text Search Headline and Rank
SELECT 
    id, kind, entity_id, title,
    ts_headline('english', body, plainto_tsquery('english', 'machine learning neural'), 'MaxWords=20') AS headline_snippet,
    ts_rank(tsv, plainto_tsquery('english', 'machine learning neural')) AS relevance_rank
FROM search_docs
WHERE tsv @@ plainto_tsquery('english', 'machine learning neural')
LIMIT 5;

-- 6. Verify Vector Embeddings in segment_vectors_blob
SELECT 
    count(*) AS total_vector_embeddings,
    octet_length(embedding) AS vector_byte_length,
    (octet_length(embedding) / 4) AS vector_dimensions
FROM segment_vectors_blob
GROUP BY octet_length(embedding)
LIMIT 5;

-- 7. Verify Auto-Increment Sequences
SELECT sequence_name, last_value
FROM information_schema.sequences
ORDER BY sequence_name;
