현재 변경사항을 분석해 컨벤션에 맞는 커밋 메시지를 작성하고 커밋합니다.

추가 메시지(선택): $ARGUMENTS

다음 순서로 진행하세요:

1. `git branch --show-current` 로 현재 브랜치를 확인합니다.
   - 브랜치 이름에서 #N 번호를 추출합니다.
   - main/main 브랜치라면 번호 없이 진행합니다.

2. `git diff --staged` 와 `git status` 로 변경사항을 파악합니다.
   - staged 변경사항이 없으면 `git add` 할 파일을 먼저 사용자에게 확인합니다.

3. 변경사항을 분석해 커밋 메시지를 결정합니다.
   - 형식: `타입/#N-brief-description: 한글 설명`
   - 타입: feat(새 기능) / fix(버그 수정) / chore(설정·의존성) / docs(문서) / refactor(리팩터링)
   - brief-description은 영문 소문자 kebab-case, 3단어 이내
   - 한글 설명은 변경 이유 중심으로 간결하게
   - 사용자가 추가 메시지를 입력했다면 내용에 반영합니다.
   - 예: `feat/#3-slash-commands: 슬래시 커맨드 추가`

4. 커밋 메시지를 사용자에게 보여주고 확인을 받은 후 커밋합니다.
