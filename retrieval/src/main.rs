//! Versioned local JSON CLI. No network, model credentials, or document ownership logic.
use rusqlite::{params, Connection, OpenFlags};
use serde::{Deserialize, Serialize};
use std::{
    collections::{HashMap, HashSet},
    io::{self, Read},
};

type Result<T> = std::result::Result<T, Box<dyn std::error::Error>>;
const VERSION: u32 = 1;
#[derive(Clone, Debug, Deserialize, Serialize)]
struct Chunk {
    id: String,
    text: String,
    page: u32,
    #[serde(default)]
    printed_page: Option<String>,
    #[serde(default)]
    section: String,
    #[serde(default)]
    vector: Vec<f64>,
}
#[derive(Deserialize)]
struct Request {
    version: u32,
    operation: String,
    database: String,
    #[serde(default)]
    fingerprint: String,
    #[serde(default)]
    chunks: Vec<Chunk>,
    #[serde(default)]
    query: String,
    #[serde(default)]
    vector: Vec<f64>,
    #[serde(default = "default_limit")]
    limit: usize,
    #[serde(default = "default_mode")]
    mode: String,
}
fn default_limit() -> usize {
    5
}
fn default_mode() -> String {
    "hybrid".into()
}
#[derive(Serialize)]
struct Hit {
    #[serde(flatten)]
    chunk: Chunk,
    score: f64,
}
fn validate_vector(v: &[f64], size: usize) -> Result<()> {
    if v.len() != size
        || v.iter().any(|x| !x.is_finite())
        || v.iter().map(|x| x * x).sum::<f64>() == 0.0
    {
        return Err(
            "invalid embedding: dimensions, finite values, and nonzero norm required".into(),
        );
    }
    Ok(())
}
fn cosine(a: &[f64], b: &[f64]) -> f64 {
    let dot: f64 = a.iter().zip(b).map(|(x, y)| x * y).sum();
    let norm =
        a.iter().map(|x| x * x).sum::<f64>().sqrt() * b.iter().map(|x| x * x).sum::<f64>().sqrt();
    dot / norm
}
fn execute(req: Request) -> Result<serde_json::Value> {
    if req.version != VERSION {
        return Err("unsupported protocol version".into());
    }
    if req.operation == "index" {
        if req.chunks.is_empty() || req.fingerprint.is_empty() {
            return Err("empty index or fingerprint".into());
        }
        let size = req.chunks[0].vector.len();
        let mut ids = HashSet::new();
        for chunk in &req.chunks {
            validate_vector(&chunk.vector, size)?;
            if chunk.id.is_empty()
                || chunk.text.is_empty()
                || chunk.page == 0
                || !ids.insert(&chunk.id)
            {
                return Err("invalid or duplicate chunk".into());
            }
        }
        let mut db = Connection::open(&req.database)?;
        let tx = db.transaction()?;
        tx.execute_batch("CREATE TABLE IF NOT EXISTS metadata(version INTEGER, fingerprint TEXT, dimensions INTEGER); CREATE TABLE IF NOT EXISTS chunks(id TEXT PRIMARY KEY, data TEXT NOT NULL); CREATE VIRTUAL TABLE IF NOT EXISTS search USING fts5(id UNINDEXED, text); DELETE FROM metadata; DELETE FROM chunks; DELETE FROM search;")?;
        tx.execute(
            "INSERT INTO metadata VALUES(?1,?2,?3)",
            params![VERSION, req.fingerprint, size],
        )?;
        for chunk in &req.chunks {
            tx.execute(
                "INSERT INTO chunks VALUES(?1,?2)",
                params![chunk.id, serde_json::to_string(chunk)?],
            )?;
            tx.execute(
                "INSERT INTO search VALUES(?1,?2)",
                params![chunk.id, chunk.text],
            )?;
        }
        tx.commit()?;
        return Ok(
            serde_json::json!({"version": VERSION,"indexed":req.chunks.len(),"dimensions":size}),
        );
    }
    if req.operation != "search" {
        return Err("unknown operation".into());
    }
    if !["lexical", "dense", "hybrid"].contains(&req.mode.as_str())
        || req.limit == 0
        || req.limit > 100
    {
        return Err("invalid mode or limit".into());
    }
    let db = Connection::open_with_flags(&req.database, OpenFlags::SQLITE_OPEN_READ_ONLY)?;
    let (version, fingerprint, size): (u32, String, usize) = db.query_row(
        "SELECT version,fingerprint,dimensions FROM metadata",
        [],
        |r| Ok((r.get(0)?, r.get(1)?, r.get(2)?)),
    )?;
    if version != VERSION || fingerprint != req.fingerprint {
        return Err("index configuration mismatch; rebuild required".into());
    }
    let mut stmt = db.prepare("SELECT data FROM chunks ORDER BY id")?;
    let chunks: Vec<Chunk> = stmt
        .query_map([], |r| r.get::<_, String>(0))?
        .map(|s| Ok(serde_json::from_str(&s?)?))
        .collect::<Result<_>>()?;
    let mut rankings: Vec<Vec<String>> = Vec::new();
    if req.mode != "dense" {
        let words: Vec<String> = req
            .query
            .split(|c: char| !c.is_alphanumeric())
            .filter(|s| !s.is_empty())
            .take(64)
            .map(|s| format!("\"{}\"", s))
            .collect();
        if !words.is_empty() {
            let mut stmt = db.prepare(
                "SELECT id FROM search WHERE search MATCH ?1 ORDER BY bm25(search),id LIMIT 100",
            )?;
            rankings.push(
                stmt.query_map([words.join(" OR ")], |r| r.get(0))?
                    .collect::<std::result::Result<_, _>>()?,
            );
        }
    }
    if req.mode != "lexical" {
        validate_vector(&req.vector, size)?;
        let mut ranked = Vec::new();
        for chunk in &chunks {
            validate_vector(&chunk.vector, size)?;
            let score = cosine(&chunk.vector, &req.vector);
            if score > 0.0 {
                ranked.push((chunk.id.clone(), score));
            }
        }
        ranked.sort_by(|a, b| b.1.total_cmp(&a.1).then(a.0.cmp(&b.0)));
        rankings.push(ranked.into_iter().take(100).map(|x| x.0).collect());
    }
    let mut scores: HashMap<String, f64> = HashMap::new();
    for ranking in rankings {
        for (rank, id) in ranking.into_iter().enumerate() {
            *scores.entry(id).or_default() += 1.0 / (61.0 + rank as f64);
        }
    }
    let mut hits: Vec<Hit> = chunks
        .into_iter()
        .filter_map(|mut chunk| {
            scores.get(&chunk.id).map(|score| {
                chunk.vector.clear();
                Hit {
                    chunk,
                    score: *score,
                }
            })
        })
        .collect();
    hits.sort_by(|a, b| {
        b.score
            .total_cmp(&a.score)
            .then(a.chunk.id.cmp(&b.chunk.id))
    });
    hits.truncate(req.limit);
    Ok(serde_json::json!({"version":VERSION,"hits":hits}))
}
fn main() {
    let result = (|| -> Result<serde_json::Value> {
        let mut input = String::new();
        io::stdin()
            .take(128 * 1024 * 1024)
            .read_to_string(&mut input)?;
        execute(serde_json::from_str(&input)?)
    })();
    match result {
        Ok(value) => println!("{}", value),
        Err(_) => {
            println!(
                "{}",
                serde_json::json!({"version":VERSION,"error":"Retrieval request failed; validate request, embeddings and index configuration."})
            );
            std::process::exit(1);
        }
    }
}
#[cfg(test)]
mod tests {
    use super::*;
    fn request(path: &str, operation: &str) -> Request {
        Request {
            version: 1,
            operation: operation.into(),
            database: path.into(),
            fingerprint: "demo".into(),
            chunks: vec![],
            query: "barrier".into(),
            vector: vec![1., 0.],
            limit: 5,
            mode: "hybrid".into(),
        }
    }
    fn chunk(id: &str, text: &str, v: Vec<f64>) -> Chunk {
        Chunk {
            id: id.into(),
            text: text.into(),
            page: 1,
            printed_page: None,
            section: "GPU".into(),
            vector: v,
        }
    }
    #[test]
    fn ranks_and_rejects_stale_index() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("index.db");
        let path = path.to_str().unwrap();
        let mut r = request(path, "index");
        r.chunks = vec![
            chunk("a", "barrier synchronizes threads", vec![1., 0.]),
            chunk("b", "memory coalescing", vec![0., 1.]),
        ];
        execute(r).unwrap();
        let hits = execute(request(path, "search")).unwrap();
        assert_eq!(hits["hits"][0]["id"], "a");
        let mut r = request(path, "search");
        r.fingerprint = "stale".into();
        assert!(execute(r).is_err());
        let mut r = request(path, "search");
        r.mode = "lexical".into();
        r.query = "zxqnone".into();
        assert_eq!(execute(r).unwrap()["hits"].as_array().unwrap().len(), 0);
    }
    #[test]
    fn invalid_vectors_and_versions() {
        assert!(validate_vector(&[0., 0.], 2).is_err());
        assert!(validate_vector(&[f64::NAN], 1).is_err());
        assert!(validate_vector(&[1.], 2).is_err());
        let mut r = request("unused", "search");
        r.version = 2;
        assert!(execute(r).is_err());
    }
}
