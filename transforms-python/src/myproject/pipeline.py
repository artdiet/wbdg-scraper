from transforms.api import Pipeline
from transforms.mediasets import MediaSetInput, MediaSetOutput

from myproject import datasets

my_pipeline = Pipeline()
my_pipeline.discover_transforms(datasets)