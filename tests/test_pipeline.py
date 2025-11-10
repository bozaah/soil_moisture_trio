import pytest
import numpy as np
from src.soil_moisture_trio.pipeline import DryWetClassifierPipeline
from src.soil_moisture_trio.config import ClassifierConfig

def test_pipeline_synthetic_data():
    # Initialize pipeline with a test configuration
    config = ClassifierConfig(grid_size=10, epochs=2, batch_size=4) # Smaller for faster test
    pipeline = DryWetClassifierPipeline(config)

    # Prepare synthetic data
    pipeline.prepare_data('synthetic')

    # Train the model
    pipeline.train()

    # Evaluate the model
    metrics = pipeline.evaluate()
    assert 'loss' in metrics
    assert 'accuracy' in metrics
    assert isinstance(metrics['loss'], float)
    assert isinstance(metrics['accuracy'], float)

    # Predict on the grid
    pred_map = pipeline.predict_grid()

    # Assertions for the prediction map
    assert isinstance(pred_map, np.ndarray)
    assert pred_map.shape == (config.grid_size, config.grid_size)
    assert np.all(np.isin(pred_map, [0, 1])) # Ensure only 0s and 1s are present

    print(f"Test completed successfully. Accuracy: {metrics['accuracy']:.4f}")
