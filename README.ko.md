# evidence-ledger

**자비스가 「75.2%」라고 답했다. 도구가 준 값은 `0.0` 이었다.**

걸음 기록은 도구가 돌았고 `ok` 였다는 것까지만 말해 준다. 모델이 그 페이지를
**읽었는지**, 목록에서 **이름만 봤는지**는 말해 주지 않는다. 두 판은 어느 로그로도
구별되지 않고, 답의 모양도 똑같다.

의존성 없는 작은 파이썬 라이브러리다. 도구 결과마다 한 줄을 남겨서 넷을 가른다.

| | |
|---|---|
| 연 것 | **vs** 본문을 읽은 것 |
| 새 출처 | **vs** 같은 출처를 또 연 것 |
| 읽기 전용 판 | **vs** 그 안에서 생긴 쓰기 |
| 도구가 준 숫자 | **vs** 답이 지어낸 숫자 |

```bash
pip install evidence-ledger
```

## 30초

```python
from evidence_ledger import Ledger
from evidence_ledger.presets import CLAUDE_CODE

ledger = Ledger(CLAUDE_CODE, run_id=job_id)

# 도구 결과가 반드시 지나는 그 한 자리에서:
ledger.record(tool_name, result, ok=ok, step=n, arguments=args)

# 답이 나온 뒤:
report = ledger.summarize(read_only=True)
```

```python
{
  "sources_read": 1,
  "sources_listed": 3,
  "answered_from_listing_only": False,
  "opened_never_read": ["https://jobs.example/p/2"],   # 눌러 들어가고 안 읽음
  "reread_sources": [],
  "read_only_violations": 0,
  "unregistered_tools": {},                            # ← 이걸 보라
}
```

숫자 대조:

```python
>>> ledger.unsupported_numbers("명지 75.2%, 성신 92.9% (평균 73.69%)")
{'75.2', '92.9', '73.69'}
```

**판정이 아니라 신호다.** 답의 숫자는 대개 페이지 **본문**에서 오고 본문은
구조화된 필드가 아니다. `answered_from_listing_only` 과 같이 읽어라 — 본문을
하나도 안 읽은 판에서 나온 「근거 없는 숫자」는 전혀 다른 이야기다.

## 왜 필드의 숫자만 걷나

처음엔 게이트를 만들려고 「답에 있는데 도구 결과엔 없는 숫자」를 셌다. **56%**가
나왔다. 쓸 수 없는 숫자였다. 답의 숫자는 대부분 본문에서 오는데 본문은 걸음
기록에 안 들어간다(메모리 보관소에 있고 재기동에 사라진다). 실제 페이지에 있던
진짜 가격이 「근거 없음」으로 찍혔다.

확증된 사례는 **1건**이었다.

그래서 게이트 대신 **재는 재료**를 낸다. 되짚을 수 없는 게이트는 처음
헛발질하는 날 꺼진다.

## 프리셋

```python
from evidence_ledger.presets import CLAUDE_CODE, PLAYWRIGHT_MCP, BROWSER_AGENT
```

출발점일 뿐이다. **첫 라이브 판에서 `ledger.unregistered()` 를 반드시 봐라.**
도구 넷으로 만든 원장이 「읽은 출처 0」을 냈던 이유가 모델이 다섯째를 집어서였고,
도구 83개 중 19개만 아는 원장은 `read_only_violations: 0` 을 내면서 아무 뜻도
없다.

도구를 등록한다는 건 하나를 정직하게 정하는 것이다 — **이 도구가 내용을 모델 앞에
갖다 놓나, 이름만 갖다 놓나.**

## 현장 기록

여기 있는 설계는 전부 실제로 터진 것이다. 한국 커머스·채용·예약 사이트를 상대로
도는 운영 에이전트에서 났고, **재는 자가 고장 나 있던 것들**까지 포함해
[`docs/FIELD-NOTES.md`](docs/FIELD-NOTES.md) 에 적었다.

- 도구 **83개 중 19개**만 아는 원장 — 본문 읽기 890건이 「안 읽음」, 「읽기 전용
  위반 0건」이 거짓
- `content`·`char_count` 는 주는데 **경로를 안 주는** 파일 리더 — 읽기가 통째로 증발
- 출처를 **리스트로** 주는 도구 둘 — 등록해 놓고 몇 주간 무동작
- 「열어 놓고 안 읽음 1」의 정체가 검색하러 들어간 **사이트 첫 화면**
- 검색도 하고 스크랩도 하는 도구 하나 — 목록으로 등록해서 쓰기가 위반 집계에서 빠짐

전부 테스트에 있고, 파일 이름이 무엇이 깨졌는지를 말한다.

## 이건 아니다

- **게이트가 아니다.** 재기만 한다. 통과·실패에 잇는 건 표본을 쌓은 뒤 당신이 정할 일
- **근거 판정 모델이 아니다.** 문장이 출처에서 따라 나오는지는 안 본다. 출처를
  읽기는 했는지를 본다. 구간 단위 판정은
  [LettuceDetect](https://github.com/KRLabsOrg/LettuceDetect)
- **프레임워크가 아니다.** 에이전트 루프도, LLM 호출도, 의존성도 없다
- **혼자서 멀티에이전트를 알지는 못한다.** 모든 줄이 `run_id` 를 들고 있어서
  **가능해질 뿐**이다 — 하위 에이전트에 같은 id로 원장을 하나씩 주고 줄을 합쳐라.
  안 그러면 하위가 읽은 것은 부모 전사에 없고, 근거 검사가 조용히 통과한다

## 선행 연구

하네스 배선이 모델 선택을 압도할 수 있다는 건 우리만의 발견이 아니다.
[Harness-Bench](https://github.com/Qihoo360/harness-bench)
([논문](https://arxiv.org/pdf/2605.27922))가 모델을 가로질러 세웠고,
[SWE-bench 과대평가](https://arxiv.org/html/2510.08996v1) 쪽 문헌이 전이 문제를
다룬다. 우리는 로컬 모델에서 통제군을 두고 독립적으로 같은 곳에 닿았고, 이
라이브러리는 거기까지 가는 데 쓴 계측기 중 하나다.

## 라이선스

Apache-2.0.
