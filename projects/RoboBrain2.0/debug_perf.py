import time
import os
import torch
import sys
from inference import UnifiedInference

# Path setup
MODEL_PATH = "/home/phl/workspace/models/RoboBrain2.0-7B"
# Use an absolute path for the image that we know exists
IMAGE_PATH = "/home/phl/workspace/fmc3-robotics/projects/RoboBrain2.0/assets/demo_nv_1.jpg" 
PROMPT = "Describe this image"

def run_benchmark(device_map_arg, description):
    print(f"\n{'='*10} Testing with {description} (device_map='{device_map_arg}') {'='*10}")
    
    if not os.path.exists(MODEL_PATH):
        print(f"Error: Model path {MODEL_PATH} does not exist.")
        return

    # 2. Load model
    print(f"Loading model from {MODEL_PATH}...")
    start_load = time.time()
    try:
        model_wrapper = UnifiedInference(
            model_id=MODEL_PATH,
            device_map=device_map_arg,
            load_in_4bit=False
        )
    except Exception as e:
        print(f"Failed to load model: {e}")
        return
    print(f"Model loaded in {time.time() - start_load:.2f} seconds.")

    # 3. Warmup
    print("Running warmup inference...")
    try:
        # Pass list of images as expected by inference method if string handling isn't sufficient, 
        # but inference code handles string: if isinstance(image, str): image = [image]
        model_wrapper.inference(PROMPT, IMAGE_PATH, task="general", enable_thinking=False)
    except Exception as e:
        print(f"Warmup failed: {e}")
        import traceback
        traceback.print_exc()

    # 4. Timed inference
    print("Running timed inference...")
    start_time = time.time()
    result = model_wrapper.inference(PROMPT, IMAGE_PATH, task="general", enable_thinking=False)
    end_time = time.time()
    
    elapsed_time = end_time - start_time
    answer = result.get("answer", "")
    
    # 5. Print stats
    # Calculate token count using the processor
    try:
        # Estimate tokens in output (answer)
        # We assume the answer is text.
        tokenized_output = model_wrapper.processor.tokenizer(answer)
        token_count = len(tokenized_output['input_ids'])
    except Exception as e:
        print(f"Could not calculate exact token count: {e}")
        token_count = len(answer.split()) # Fallback

    print(f"-"*30)
    print(f"Time taken: {elapsed_time:.4f} seconds")
    print(f"Generated text length: {len(answer)} chars")
    print(f"Estimated generated tokens: {token_count}")
    print(f"Output snippet: {answer[:100].replace(chr(10), ' ')}...")
    print(f"-"*30)
    
    # Clean up
    del model_wrapper
    torch.cuda.empty_cache()
    
def main():
    print("Starting performance debug script...")
    
    # Run 1: device_map="auto"
    run_benchmark("auto", "Auto Device Map")
    
    # Run 2: device_map="cuda:0"
    run_benchmark("cuda:0", "Single GPU (cuda:0)")

if __name__ == "__main__":
    main()
