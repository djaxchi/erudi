from datetime import datetime
import logging
from transformers import TrainerCallback

from ..models.TrainingJob import TrainingJob

class ProgressCallback(TrainerCallback):
    def __init__(self, training_job_id, db_factory):
        super().__init__()
        logging.info("Initializing ProgressCallback")
        self.training_job_id = training_job_id
        self.db_factory = db_factory
        self.start_time = None
        logging.info(f"ProgressCallback initialized with job ID: {self.training_job_id}")

    def on_train_begin(self, args, state, control, **kwargs):
        """Called at the beginning of training"""
        self.start_time = datetime.now()
        logging.info(f"Training started at {self.start_time}")

        try:
            # Calculate progress percentage
            if state.max_steps > 0:
                percent = 100 * state.global_step / state.max_steps
            elif state.num_train_epochs > 0:
                percent = 100 * state.epoch / state.num_train_epochs
            else:
                percent = 0

            # Calculate time metrics
            elapsed = (datetime.now() - self.start_time).total_seconds() if self.start_time else 0
            eta = None
            if percent > 0:
                estimated_total = elapsed / (percent / 100)
                eta = estimated_total - elapsed

            # Only log occasionally to avoid flooding logs
            if state.global_step % 10 == 0:
                logging.info(f"Progress: {percent:.1f}%, Step: {state.global_step}, "
                            f"Elapsed: {elapsed:.1f}s, ETA: {eta:.1f if eta else 0}s")

            # Update database
            db = self.db_factory()
            try:
                job = db.query(TrainingJob).filter(TrainingJob.id == self.training_job_id).first()
                if job:
                    job.progress = percent
                    job.time_elapsed = elapsed
                    job.time_left = eta
                    db.commit()
            finally:
                db.close()
        except Exception as e:
            logging.error(f"Error in ProgressCallback.on_log: {e}")
            # Continue training even if progress tracking fails

    def on_log(self, args, state, control, logs=None, **kwargs):
        """Called when logs are available"""
        try:
            # Calculate progress percentage
            if state.max_steps > 0:
                percent = 100 * state.global_step / state.max_steps
            elif state.num_train_epochs > 0:
                percent = 100 * state.epoch / state.num_train_epochs
            else:
                percent = 0

            # Calculate time metrics
            elapsed = (datetime.now() - self.start_time).total_seconds() if self.start_time else 0
            eta = None
            if percent > 0:
                estimated_total = elapsed / (percent / 100)
                eta = estimated_total - elapsed

            # Only log occasionally to avoid flooding logs
            if state.global_step % 10 == 0:
                logging.info(f"Progress: {percent:.1f}%, Step: {state.global_step}, "
                            f"Elapsed: {elapsed:.1f}s, ETA: {eta:.1f if eta else 0}s")

            # Update database
            db = self.db_factory()
            try:
                job = db.query(TrainingJob).filter(TrainingJob.id == self.training_job_id).first()
                if job:
                    job.progress = percent
                    job.time_elapsed = elapsed
                    job.time_left = eta
                    db.commit()
            finally:
                db.close()
        except Exception as e:
            logging.error(f"Error in ProgressCallback.on_log: {e}")
            # Continue training even if progress tracking fails