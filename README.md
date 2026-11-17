# video-previs-workflow

Claude Code와 Codex에서 함께 사용하는 프리비즈 기반 영상 제작 스킬입니다. 아이디어·대본·콘티·참고 영상에서 시작하고, **스토리 설계 → 프리비즈 검토 → 실제 외형 이미지 검토 → 샷 키프레임 검토 → 생성 → 편집·검수**로 진행합니다. 기존 이미지, 신규 이미지, 혼합 제작을 지원합니다.

독립 작성한 워크플로와 보조 도구를 포함하며 다른 프리비즈 스킬을 설치할 필요가 없습니다. 사용자별 이미지·영상·사업 자료나 제3자 스킬 코드는 포함하지 않습니다.

## 설치

저장소를 clone한 뒤 아래 **같은 스킬 폴더 전체**를 각 호스트의 프로젝트 스킬 경로로 복사합니다. `PROJECT`를 실제 작업 프로젝트 경로로 설정하세요. 기존 설치가 있다면 덮어쓰지 말고 차이를 확인하세요.

```sh
git clone https://github.com/devHDK/video-previs-workflow.git
cd video-previs-workflow
PROJECT='/absolute/path/to/your/project'
mkdir -p "$PROJECT/.agents/skills" "$PROJECT/.claude/skills"
# 새 설치만: 목적지 존재 시 먼저 확인
[ ! -e "$PROJECT/.agents/skills/video-previs-workflow" ] && cp -R skills/video-previs-workflow "$PROJECT/.agents/skills/"
[ ! -e "$PROJECT/.claude/skills/video-previs-workflow" ] && cp -R skills/video-previs-workflow "$PROJECT/.claude/skills/"
# 선택: 기획 단계 스토리 설계 스킬
[ ! -e "$PROJECT/.agents/skills/story-design" ] && cp -R skills/story-design "$PROJECT/.agents/skills/"
[ ! -e "$PROJECT/.claude/skills/story-design" ] && cp -R skills/story-design "$PROJECT/.claude/skills/"
```

`story-design`은 콘셉트에서 **핵심 목적 → 유도할 시청자 행동 → 둘에 맞는 스토리 구조**를 먼저 정하고 시간별 비트를 설계합니다. video-previs-workflow는 승인된 스토리 설계서를 요구하지만, story-design 설치는 선택입니다(설계서 필드만 확인).

Agent Skills installer를 사용하는 경우 아래 방식도 사용할 수 있습니다. 설치 대상 호스트와 프로젝트/전역 범위는 설치기의 선택 화면에서 확인하세요. 실제 설치기 검증 여부는 [검증 기록](VALIDATION.md)을 참고하세요.

```sh
npx skills add devHDK/video-previs-workflow --skill video-previs-workflow
```

Codex에서는 `$video-previs-workflow`, Claude Code에서는 `/video-previs-workflow`로 호출합니다. 목록에 없으면 호스트의 스킬 새로고침/새 세션 후 설치 경로를 확인하세요. MCP 연결과 인증은 각 호스트에서 따로 설정합니다. 이 스킬 설치가 Blender나 생성 서비스를 자동으로 설치·결제하지는 않습니다.

## 사용 예시

> 이 캐릭터 사진과 새로운 마을 배경으로 12초 영상을 만들자. 먼저 점프 동작과 카메라를 프리비즈로 보고 싶어. 캐릭터 사진은 그대로 쓰고 배경 이미지는 검토 후 확정하자.

> 이 콘셉트로 저장을 유도하는 22초 에피소드 스토리부터 설계하자.

> 이 참고 영상을 우리 캐릭터로 바꿔서 구도·동작·타이밍은 그대로 다시 만들자.

> 기존 프로젝트 상태를 읽고 이어서 진행해. 승인한 외형은 유지하고 두 번째 컷의 카메라만 바꾸자.

> 영상은 웹 Unlimited로 내가 직접 생성할게. 업로드할 파일과 설정을 정리해 줘.

## 제작 단계

| 단계 | 승인 대상 | 검사 도구 |
|---|---|---|
| 0. 스토리 | 핵심 목적·시청자 행동·구조·시간별 비트 (참고 영상 경로는 분해서) | `check_story.py`, `gate.py reference` |
| 1. 프리비즈 | Blender 렌더 프레임·영상, 콘티 대조 시트 | `validate_spec.py`, `render_previs.py` 지오메트리 감사 |
| 2. 외형 | 역할별 실제 이미지(캐릭터 앞·뒤 시트, 세트, 소품) | — |
| 3. 샷 키프레임 | 샷별 시작 프레임 + 공유 역할별 연속성 검토 | `media.py continuity` |
| 4. 생성 | 작업 단위 범위·비용 상한·시도 한도·재시도 예비분 | `gate.py ready`, `gate.py submit` |
| 5. 편집·QA | 최종 MP4, 테이크↔프리비즈 대조 | `media.py pair`, `media.py assemble` |

`gate.py`가 오류를 내면 유료 영상 생성을 제출하지 않습니다. 승인 기록·자산 버전·작업 상태·예산은 프로젝트 파일에 남겨 다른 호스트에서 이어서 진행할 수 있습니다.

## 포함 기능과 범위

- 이야기·샷 계획, 네 가지 creative review(스토리·프리비즈·외형·키프레임), 자산 버전 및 호스트 간 재개 기록.
- 참고 영상 재현 경로: 컷 감지로 샷별 프레임·클립·분해 초안을 만들고, 승인된 분해서가 스토리 설계를 대신하며, 프리비즈 샷 길이를 참고 컷에 맞춰 검사.
- Python 장면 명세 검사·변경 컷 식별, Blender 도형·캡슐 대역, 이동·추적 카메라와 렌즈 키, 프리비즈 렌더.
- 키프레임 연속성: 여러 샷에 나오는 역할마다 키프레임을 한 줄로 모은 시트를 만들고, 승인 해시가 현재 키프레임과 일치해야 게이트를 통과.
- 유료 생성 게이트: 프로젝트 준비 상태, 작업별 견적·상한·재시도 예비분, 같은 장소의 연속 샷을 한 테이크로 묶는 시퀀스 작업 검사.
- 수동 웹 생성 경로: 웹 전용 요금제(예: Higgsfield Unlimited)를 쓸 때 업로드 순서대로 입력과 `request.md`를 묶고, 사람이 떨어뜨린 결과 하나를 디코드·해시 확인 후 반입. 웹 앱 자동화는 하지 않습니다.
- FFmpeg 프레임 추출·비교·프리비즈/테이크 대조 시트·컷 정규화·프레임 길이 편집(인점·±10% 속도)·준비된 음성 믹스와 선택형 자막 결합.
- 연결된 생성 도구의 실제 스키마에 맞춘 작업, 비용·시도 한도와 중복 제출 방지 절차.
- 실제 이미지·영상·음성·립싱크 생성은 사용 가능한 외부 도구가 수행합니다. 공급자 API 클라이언트나 자동 결제 제한 시스템을 포함하지 않습니다.

| 스크립트 | 역할 |
|---|---|
| `story-design/scripts/check_story.py` | 스토리 설계서 구조 검사 |
| `video-previs-workflow/scripts/doctor.py` | Python·Blender·FFmpeg 사용 가능 여부 |
| `validate_spec.py` | 장면 명세 검사, 이전 버전 대비 변경 샷 식별 |
| `render_previs.py` | Blender 백그라운드 프리비즈 렌더·지오메트리 감사 |
| `media.py` | `probe` `extract` `encode` `assemble` `compare` `pair` `continuity` `cuts` |
| `gate.py` | `reference` `ready` `submit` (상태를 읽기만 하고 수정하지 않음) |
| `handoff.py` | 수동 웹 생성 `pack` / `ingest` (상태를 수정하지 않음) |

명령 예시와 입력 형식은 [local-tools.md](skills/video-previs-workflow/references/local-tools.md)에 있습니다.

로컬 도구는 Python 3.10+(pip 의존성 없음), Blender 4.2+의 EEVEE Next 인터페이스(5.3.0에서 실행 확인), FFmpeg/ffprobe를 대상으로 작성했습니다. 실제 검증 범위는 검증 기록에서 확인하세요. 렌더러는 카메라 경로·대상 추적·렌즈 변화와 단순 대역 동작을 지원합니다. 화면 이탈·중심점 가림·지정 구간 지면 접촉을 검사하고 빠른 검토용 스틸을 출력합니다. 정교한 걷기·손동작·표정은 프로젝트별 Blender 작업이 필요합니다. 생성 영상의 프레임 단위 동일성은 보장하지 않습니다.

## 개발 검증

```sh
python3 -m unittest discover -s tests -v
python3 skills/video-previs-workflow/scripts/doctor.py
python3 skills/video-previs-workflow/scripts/validate_spec.py skills/video-previs-workflow/assets/example-scene.json
python3 skills/story-design/scripts/check_story.py skills/story-design/assets/example-story.json
```

실제 실행 결과와 검증하지 않은 범위는 [VALIDATION.md](VALIDATION.md)에 기록합니다.

유료 제작 전에 작업별 범위·비용 상한·최대 시도 횟수를 승인합니다. 스킬을 설치하거나 실행하겠다는 말만으로 생성 크레딧 사용을 승인한 것으로 처리하지 않습니다.

## 라이선스

[MIT](LICENSE)
