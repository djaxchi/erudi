from datetime import datetime
import logging
from transformers import TrainerCallback

from ..models.TrainingJob import TrainingJob

class TrainingProgressCallback(TrainerCallback):
    def __init__(self, training_job_id, db_factory):
        super().__init__()
        logging.info("Initializing ProgressCallback")
        self.training_job_id = training_job_id
        self.db_factory = db_factory
        self.start_time = None
        self.last_update_time = None
        logging.info(f"ProgressCallback initialized with job ID: {self.training_job_id}")

    def _update_progress(self, state):
        logging.info(f"UPDATING PROGRESS CALLBACK")

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

            eta_str = f"{eta:.1f}" if eta is not None else "N/A"
            logging.info(f"Progress: {percent:.1f}%, Step: {state.global_step}, "
                f"Elapsed: {elapsed:.1f}s, ETA: {eta_str}s")

            # Update database
            db = self.db_factory()
            try:
                job = db.query(TrainingJob).filter(TrainingJob.id == self.training_job_id).first()
                if job:
                    job.progress = percent
                    job.time_elapsed = elapsed
                    job.time_left = eta if eta is not None else 0.0
                    db.commit()
                    logging.debug(f"Updated training job {self.training_job_id}: {percent:.1f}% complete")
            finally:
                db.close()
                
        except Exception as e:
            logging.error(f"Error in ProgressCallback._update_progress: {e}")
            # Continue training even if progress tracking fails

    def on_train_begin(self, args, state, control, **kwargs):
        """Called at the beginning of training"""
        self.start_time = datetime.now()
        self.last_update_time = self.start_time
        logging.info(f"Training started at {self.start_time}")
        # Initialize progress at 0%
        self._update_progress(state)

    def on_step_begin(self, args, state, control, **kwargs):
        """Called at the beginning of each training step - most frequent callback"""
        current_time = datetime.now()
        
        self._update_progress(state)
        self.last_update_time = current_time

    def on_step_end(self, args, state, control, **kwargs):
        """Called at the end of each training step"""
        current_time = datetime.now()
        
        self._update_progress(state)
        self.last_update_time = current_time

    def on_log(self, args, state, control, logs=None, **kwargs):
        """Called when logs are available - update progress every 3 seconds"""
        current_time = datetime.now()
        
        self._update_progress(state)
        self.last_update_time = current_time


    def on_substep_end(self, args, state, control, **kwargs):
        """Called at the end of each substep - update progress every 2 seconds"""
        current_time = datetime.now()
        
        self._update_progress(state)
        self.last_update_time = current_time

    def on_epoch_end(self, args, state, control, **kwargs):
        """Called at the end of each epoch - update progress every 2 seconds"""
        current_time = datetime.now()
        
        self._update_progress(state)
        self.last_update_time = current_time


    def on_train_end(self, args, state, control, **kwargs):
        """
        Event called at the end of training.
        """
        current_time = datetime.now()

        self._update_progress(state)
        self.last_update_time = current_time