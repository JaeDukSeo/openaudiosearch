use anyhow::Context;
use oas_common::types::{Media, Post};
use oas_common::{Record, RecordMap, Resolver, UntypedRecord};

use crate::couch::durable_changes::ChangesOpts;
use crate::jobs::{typs as job_typs, JobManager};
use crate::State;

const DURABLE_ID: &str = "core.jobs";

pub async fn process_changes(state: State, infinite: bool) -> anyhow::Result<()> {
    let opts = ChangesOpts {
        infinite,
        ..Default::default()
    };
    let mut changes = state.db_manager.durable_changes(DURABLE_ID, opts).await;
    while let Some(batch) = changes.next().await? {
        process_batch(&state, batch.into_inner())
            .await
            .context("Failed to process changes batch for jobs")?;
    }
    Ok(())
}

pub async fn process_batch(state: &State, batch: Vec<UntypedRecord>) -> anyhow::Result<()> {
    let mut sorted = RecordMap::from_untyped(batch)?;
    let mut posts = sorted.into_vec::<Post>();
    let medias = sorted.into_vec::<Media>();
    state
        .db
        .resolve_all_refs(&mut posts)
        .await
        .context("failed to resolve refs")?;

    for record in posts.into_iter() {
        let res = on_post_change(state, record).await;
        log_if_error(res);
    }

    for record in medias.into_iter() {
        let res = on_media_change(state, record).await;
        log_if_error(res);
    }

    Ok(())
}

async fn on_post_change(state: &State, record: Record<Post>) -> anyhow::Result<()> {
    // Check for post-level jobs.
    // Logic is: Create an NLP job if record.value.nlp is serde_json::Value::Null
    // and no NLP job is pending for this record.
    let typ = job_typs::NLP;
    if let Some(_opts) = record.meta().jobs().setting(typ) {
        if record.value.nlp.is_null() && !has_pending(&state.jobs, typ, record.guid()).await {
            let job = job_typs::nlp_job(&record, None);
            state.jobs.create_job(job).await?;
        }
    }

    Ok(())
}

async fn on_media_change(state: &State, record: Record<Media>) -> anyhow::Result<()> {
    let typ = job_typs::ASR;
    if let Some(_opts) = record.meta().jobs().setting(typ) {
        if record.value.transcript.is_none() && !has_pending(&state.jobs, typ, record.guid()).await
        {
            let job = job_typs::asr_job(&record, None);
            state.jobs.create_job(job).await?;
        }
    }
    Ok(())
}

async fn has_pending(jobs: &JobManager, typ: &str, guid: &str) -> bool {
    match jobs.pending_jobs(guid, typ).await {
        Err(_) => false,
        Ok(list) => !list.is_empty(),
    }
}

fn log_if_error<A>(res: anyhow::Result<A>) {
    match res {
        Ok(_) => {}
        Err(err) => log::error!("{:?}", err),
    }
}
