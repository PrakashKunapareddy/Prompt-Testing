class ModelFactory:
    model_mapping: dict = {}

    def __init__(self, model_mapping):
        self.model_mapping = model_mapping

    def create_model_instance(self, model_map_name, **kwargs):
        # print(self.model_mapping, model_map_name)
        model = self.model_mapping.get(model_map_name)
        if model:
            try:
                return model(**kwargs)
            except TypeError as e:
                raise TypeError(f"Error creating model instance for '{model_map_name}': {e}")
        else:
            raise ValueError(f"Model '{model_map_name}' not found in the model mapping.")