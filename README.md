# Lux-AI
[Kaggle Competition](https://www.kaggle.com/c/lux-ai-2021/overview)\
[Challenge Repository](https://github.com/Lux-AI-Challenge/Lux-Design-S1)\
[Challenge Viewer](https://github.com/Lux-AI-Challenge/Lux-Viewer-S1)

## Testing

We use `pytest` for unit testing in this project. Test files are named with the pattern `Test*.py` and are located in each separate module.

### Running Tests

Before merging or pushing changes, please run the unit tests using the following command in the main directory:

```
pytest
```

This will discover and run all test files across the project.

## Logging

This project uses Python's built-in `logging` module for tracking events and debugging.

### Adding Log Entries

To add a logging entry, use the `logging.info()` function in the corresponding section of the code. For example:

```python
import logging

logging.info("This is an informational log message")
```

You can also use other log levels such as `logging.debug()`, `logging.warning()`, `logging.error()`, and `logging.critical()` as appropriate for the severity of the message.
