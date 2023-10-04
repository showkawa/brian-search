import os
import argparse

#Usage
#python generate_pdg.py --startpath /path/to/your/project --output_file output.txt

# Specify the directories and files to ignore
ignore_list = ['node_modules', '.git', '*.pyc','*.md']

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--startpath', required=True, help='The start path of the project')
    parser.add_argument('--output_file', default=None, help='The output file')
    args = parser.parse_args()

    print("---args--- ", args)

    if not args.output_file:
        generate(args.startpath, None)
    else:
        generate(args.startpath, args.output_file)    

def generate(startpath, output_file=None):
    # Get the project name from the startpath
    project_name = os.path.basename(os.path.normpath(startpath))
    print("---path--- ", os.path.normpath(startpath))
    print("---project_name--- ", project_name)
    # If output_file is not specified, save it to the current directory
    if output_file is None:
        output_file = "{}_psd.txt".format(project_name)

    with open(output_file, 'w') as f:
        for root, dirs, files in os.walk(startpath):
            # Skip directories and files in the ignore list
            dirs[:] = [d for d in dirs if d not in ignore_list]
            files = [f for f in files if f not in ignore_list]

            level = root.replace(startpath, '').count(os.sep)
            indent = ' ' * 4 * (level)
            f.write('{}{}/\n'.format(indent, os.path.basename(root)))
            subindent = ' ' * 4 * (level + 1)
            for f_name in files:
                f.write('{}{}\n'.format(subindent, f_name))


if(__name__ == "__main__"):
    main()