"""

Quick-and-dirty script for downloading, building, and grading Java class assignments

To do: replace the text in classlist.txt with a list of your own student github login names

To use: provide your org name,  the repo prefix, and the grades JSON filename as arguments, for example:

python grader.py mctc_itec assignment_7_classes week_7.json

TODO: either check modification dates for the test files and grades JSON file
OR copy in the original test files/grades JSON to prevent cheating, or students modifying tests.

Not tested on Windows.

If the student's code is already downloaded, it won't be graded.
Suggest deleting any downloaded code for this assignment and downloading everying fresh.

A lot of output is dumped into raw_output.txt.

Requires Python 3.7 or later. Updgrade if it's failing on the capture_output argument in subprocess.run.


"""

import sys, subprocess, json, os, re


if len(sys.argv) != 4:
    sys.exit("""You must provide the org name and the repo prefix and the name of the grades.json file. E.g.
    python grader.py mctc-itec assignment_3_functions week_3.json""")

org_name = sys.argv[1]
repo_prefix = sys.argv[2]
grade_json_file = sys.argv[3]

class_list_file = 'classlist.txt'
raw_output_file = 'raw_output.txt'
grades_file = 'grades.txt'

def main():

    # Read list of students

    print('\nReading student list...')

    with open(class_list_file, 'r') as f:

        students = [ student.strip() for student in f.readlines() if not student or student[0] is not '#']

    results = dict( zip (students, [0] * len(students)) )
    grades = dict( zip (students, [0] * len(students)) )

    # For each student, download ther code
    # The repo URL will be in the form of
    # https://github.com/ORGNAME/PREFIX_STUDENTGITHUBID

    print('\nDownloading student code repositories\n')

    url_template = 'https://github.com/%s/%s-%s'

    successfully_downloaded_repos = []

    for student_github in students:

        repo_url = url_template % (org_name, repo_prefix, student_github)
        destination = os.path.join(repo_prefix, student_github)
        command = ['git', 'clone', '--recursive', repo_url, destination ]
        clone_result = subprocess.run(command, capture_output=True)
        if clone_result.returncode != 0:
            results[student_github] = 'Error cloning code from GitHub, ' + str(clone_result.stderr)
            if 'already exists and is not an empty directory.' in str(clone_result.stderr):
                print('Unable to clone %s - it is already downloaded. WARNING! it will NOT be graded.' % (student_github) )
            elif 'remote: Repository not found' in str(clone_result.stderr):
                print('No code for %s found at GitHub.' % student_github)
            else:
                print('Unable to clone %s for reason %s %s ' % (repo_url, clone_result.stdout, clone_result.stderr ) )
        else:
            successfully_downloaded_repos.append(student_github)

    print('\nDownloaed these repositories:\n', ', '.join(successfully_downloaded_repos))


    # For each repo, build and run tests

    print('\nBuilding and running tests, please wait...\n')

    successfully_built_repos = []

    test_fail_messages = {}

    for student_github in successfully_downloaded_repos:

        project_dir = os.path.join(repo_prefix, student_github)
        mvn_test_cmd = ['mvn', '-q', '-f', project_dir, 'test']
        build_result = subprocess.run(mvn_test_cmd, capture_output=True)
        if build_result.returncode != 0:
            results[student_github] = str(build_result.stderr)
            if 'There are test failures' in str(build_result.stdout):
                print('Code built with test failures and/or errors for %s' % student_github)
                successfully_built_repos.append(student_github)  # Still have code that runs, even if not all tests pass.
            else:
                print('Error building code for %s' % (student_github))                  # the code did not compile.
        else:
            print('All tests passed for %s' % student_github)
            successfully_built_repos.append(student_github)


    print('\nCompiled and ran tests for these repositories:\n', ', '.join(successfully_built_repos))


    # TODO check for edited tests/grade files or insert student code into onstructor copy.


    # For each repo that was build, use the grades_week_1.json and the output in the test reports to figure out the grade.

    for student_github in successfully_built_repos:
        project_dir = os.path.join(repo_prefix, student_github)
        student_result, total_points = calc_grade(project_dir)

        results[student_github] = str(student_result) + '\n' + str(results[student_github])
        grades[student_github] = total_points

    with open(grades_file, 'w') as f:
        for s, g in grades.items():
            f.write('%s, %f\n' % (s, g))

    print('\nNumber grades written to ' + grades_file )

    with open(raw_output_file, 'w') as f:

        for student in students:

            f.write('GitHub username for student ' + student + '\n')
            f.write('Number grade: %f\n' % grades[student])
            f.write('Messages: %s' % results[student])
            f.write('\n\n%s\n\n' % ('*' * 80) )

    print('Raw output written to ' + raw_output_file )

    print('Grade summary:\n' + str(grades))



def calc_grade(project_location):
    # yuck

    json_file = os.path.join(project_location, 'grades', grade_json_file)
    try:
        scheme = json.load(open(json_file))
    except:
        sys.exit('Can\'t find JSON file. Looked in /grades/ directory of student repo for file named ' + grade_json_file)

    total_points = 0
    results = {}

    test_set = grade_json_file.split('.')[0]  # yuck. The test_set is the package name for the student's Java files and it's the same as the JSON filename, in the labs I've created anyway. E.g. test_set is week_3 and the grade scheme is week_3.json.

    all_questions = scheme['questions']

    for item in all_questions:

        test_filenames = item['test_file']    # This is either a String or list. Ensure it is list
        java_filename = item['java_file']

        if type(test_filenames) is str:
            test_filename_list = [ test_filenames ]
        else:
            test_filename_list = test_filenames

        points_avail = item['points']

        run = 0
        passing_tests = 0
        errors = 0
        failures = 0

        for test_filename in test_filename_list:
            try:
                report_filename = '%s.%s.txt' % (test_set, test_filename)
                report_location = os.path.join(project_location, 'target', 'surefire-reports', report_filename)

                with open(report_location) as f:
                    report = f.readlines()
                    q_run, q_errors, q_failures = extract(report[3]) # ugh
                    # So question is worth e.g. 5 points. 3 tests, 1 fails. Student gets 5/3 * 2 points for this
            except IOError:
                q_run, q_errors, q_failures = (0, 0, 0) # ugh

            run = run + q_run
            errors = errors + q_errors
            failures = failures + q_failures

        # For all tests for this question,
        passing_tests = run - (errors + failures)
        if run == 0:
            points_for_question = 0
        else:
            points_for_question = ( points_avail / run ) * passing_tests
        total_points += points_for_question
        results[java_filename] = points_for_question


    return results, total_points


def extract(line) :

    run = re.search('(?<=Tests run: )\d+', line).group(0)
    errors = re.search('(?<=Failures: )\d+', line).group(0)
    failures = re.search('(?<=Errors: )\d+', line).group(0)
    #print(run,errors, failures)
    return int(run), int(errors), int(failures)


main()
